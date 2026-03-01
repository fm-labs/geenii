import asyncio
import logging
import os
from typing import List, AsyncGenerator

import pydantic

from geenii.ai import generate_chat_completion
from geenii.chat.chat_bots import BotInterface
from geenii.chat.chat_models import ToolCallResultContent, ContentPart, TextContent, ToolCallContent
from geenii.config import DEFAULT_COMPLETION_MODEL, DATA_DIR
from geenii.datamodels import ModelMessage, ChatCompletionRequest
from geenii.memory import ChatMemory
from geenii.rt import init_builtin_tools
from geenii.skills import SkillRegistry
from geenii.tools import execute_tool_call, ToolRegistry
from geenii.tts import tts_say_cli
from geenii.utils.json_util import read_json

logger = logging.getLogger(__name__)

DEFAULT_WIZARD_SYSTEM_PROMPT = """
You are an AI assistant that MUST use available tools when they are relevant.

CORE RULES:

1. NEVER answer from internal knowledge if a tool exists that can provide up-to-date, factual, or external information.
2. ALWAYS evaluate whether a tool should be used BEFORE generating a final response.
3. If a suitable tool exists, you MUST call the tool instead of answering directly.
4. Only produce a final natural-language answer AFTER tool results are returned.
5. Follow the tool calling format EXACTLY.

DECISION PROCESS:

Step 1 — Analyze user intent.
Step 2 — Check available tools.
Step 3 — If any tool can help, return a tool call with the appropriate arguments.
Step 4 — If no tools are relevant, answer the user's question directly.
"""


def message_to_prompt(message: str | list[ContentPart]) -> str | None:
    if message is None:
        return None
    elif isinstance(message, str):
        return message
    elif isinstance(message, list):
        return " ".join([content.to_text() for content in message])
    else:
        raise ValueError("Unsupported message format")


# class BaseWizardStep:
#     """
#     Base class for a wizard step. A step represents a single action or decision point in the wizard's process.
#     """
#
#     async def run(self) -> AsyncGenerator[ContentPart, None]:
#         """
#         The __aiter__ method allows the step to be used as an asynchronous generator that yields ContentPart objects.
#         This can be used to generate intermediate content parts as the step is executed.
#         """
#         yield TextContent(text="BaseWizardStep: Not implemented")
#
# class AnonymousStep:
#     name: str
#     callable: Callable[[ModelMessage], AsyncGenerator[ContentPart, None]]
#
#     async def run(self) -> AsyncGenerator[ContentPart, None]:
#         return self.callable(ModelMessage(role="assistant", content=[]))

class HumanInTheLoopHandler:
    """
    This class can be used to handle human-in-the-loop interactions for tool call approvals or other decision points in the wizard's process.
    """

    async def request_tool_execution(self, tool_name: str, arguments: dict, call_id: str) -> bool:
        """
        This method can be overridden to implement custom logic for approving or rejecting tool execution requests.
        By default, it approves all tool execution requests.
        """
        return True


class Wizard(BotInterface):

    def __init__(self, name, model: str = None, system_prompt: str = None, description: str = None,
                 tool_registry: ToolRegistry = None, skill_registry: SkillRegistry = None,
                 context_id: str = None, memory: ChatMemory = None, hidl: HumanInTheLoopHandler = None):

        self.name = name
        self.description = description
        self.model = model or DEFAULT_COMPLETION_MODEL
        self.system_prompt = system_prompt or DEFAULT_WIZARD_SYSTEM_PROMPT
        self.message_history: List[ModelMessage] = []
        self.memory = memory or None
        self.context_id = context_id or None

        self._tool_registry = tool_registry or ToolRegistry()
        self._skill_registry = skill_registry or SkillRegistry()
        self._tasks: asyncio.Queue[dict] = asyncio.Queue()
        self._hidl = hidl or HumanInTheLoopHandler()

    def __repr__(self):
        return f"Wizard(name={self.name}, context_id={self.context_id}, model={self.model}, tools={self.tools.list_tool_names()}, skills={self.skills.list_skill_names()})"

    @property
    def tools(self) -> ToolRegistry:
        return self._tool_registry

    @property
    def skills(self) -> SkillRegistry:
        return self._skill_registry

    async def prompt(self, message: str | list[ContentPart]) -> AsyncGenerator[ModelMessage, None]:
        """Process an incoming message and generate a response by enqueuing tasks to the internal queue and processing them sequentially."""
        # enqueue new llm task
        await self._tasks.put({"task": "ask_llm", "arguments": {"message": message}})
        # process the queue and yield messages
        async for msg in self._process_queue():
            yield msg

    async def _process_queue(self) -> AsyncGenerator[ModelMessage, None]:
        """Process tasks from the internal queue sequentially. Yields content parts generated by the tasks. Exits when the queue is empty."""
        i = 0
        while self._tasks.qsize() > 0:
            task = await self._tasks.get()
            i += 1
            logger.info(f"Task #{i}")
            try:
                if task["task"] == "ask_llm":
                    async for msg in self._ask_llm(**task["arguments"]):
                        yield msg
                #elif task["task"] == "process_tool_results":
                #    async for msg in self._process_tool_results(**task["arguments"]):
                #        yield msg
                elif task["task"] == "call_tool":
                    async for msg in self._call_tool(**task["arguments"]):
                        yield msg
                elif task["task"] == "finalize":
                    async for msg in self._finalize():
                        yield msg
                else:
                    logger.critical(f"Unknown task type: {task['task']}")
            except Exception as e:
                logger.exception(f"Error processing task {task['task']}: {str(e)}", exc_info=e)
                # todo handle exceptions properly, e.g. by yielding an error message
                yield ModelMessage(role="assistant",
                                   content=[TextContent(text=f"An error occurred while processing the task: {str(e)}")])
            finally:
                self._tasks.task_done()


    def _request_completion(self, request):
        response = generate_chat_completion(request=request, tool_registry=self._tool_registry,)
        return response

    async def _ask_llm(self, message: str | list[ContentPart]) -> AsyncGenerator[ModelMessage, None]:
        """Generate LLM chat completion response in the current context. Handles tool calls"""
        full_system_prompt = self._build_system_prompt()
        #print(full_system_prompt)
        prompt = message_to_prompt(message)
        allowed_tools = set(self._tool_registry.list_tool_names()) # todo filter tools
        input_messages = list(self.message_history[:10]) # snapshot of the current message history (last 10 messages)

        # run sync task in thread pool to avoid blocking the event loop while waiting for the response
        request = ChatCompletionRequest(prompt=prompt,
                                        model=self.model,
                                        system=full_system_prompt,
                                        messages=input_messages, # snapshot of the current message history
                                        tools=allowed_tools,
                                        context_id=self.context_id
                                        )
        response = await asyncio.to_thread(self._request_completion, request)
        logger.info(f"Received model response for prompt '{prompt}' with {len(response.output)} content parts.")

        tool_calls = 0
        output_parts: List[ContentPart] = response.output
        for item in response.output:
            # handle tool calls
            if isinstance(item, ToolCallContent):
                tool_calls += 1
                # enqueue tool call for processing and yield a placeholder message until the tool result is available
                await self._tasks.put({"task": "call_tool", "arguments": {"tool_name": item.name, "arguments": item.arguments}})


        # add user request to message history
        user_message = ModelMessage(role="user", content=[TextContent(text=prompt)])
        self.message_history.append(user_message)

        # add model response to message history
        bot_message = ModelMessage(role="assistant", content=output_parts)
        self.message_history.append(bot_message)

        # yield the output message
        yield bot_message

        # if there were tool calls, we can optionally trigger a follow-up action,
        # e.g. by enqueuing another task to process the tool results or to ask the LLM for the next step based on the tool results.
        if tool_calls > 0:
            logger.info(f"{tool_calls} tool calls were made in the response. Enqueuing follow-up task to process tool results.")
            await self._tasks.put({"task": "finalize", "arguments": {}})


    async def _call_tool(self, tool_name: str, arguments: dict, call_id: str = None) -> AsyncGenerator[ModelMessage, None]:
        """Call a tool and yield the result as a message."""
        tool_usage_approved = await self.request_tool_execution(tool_name=tool_name, arguments=arguments, call_id=call_id)
        if not tool_usage_approved:
            logger.critical(f"Tool execution for {tool_name} was rejected by the request_tool_execution method.")
            tool_result = {"error": "Tool execution rejected."}
            yield ModelMessage(role="tool", content=[ToolCallResultContent(name=tool_name, arguments=arguments, result=tool_result, call_id=call_id)])
            return

        logger.info(f"Calling tool {tool_name} with arguments {arguments}")
        try:
            tool_result = execute_tool_call(self._tool_registry, tool_name, **arguments)
            logger.info(f"Tool {tool_name} returned result: {tool_result}")
        except Exception as e:
            logger.exception(f"Error executing tool {tool_name}", exc_info=e)
            tool_result = {"error": str(e)}
        yield ModelMessage(role="tool", content=[ToolCallResultContent(name=tool_name, arguments=arguments, result=tool_result, call_id=call_id)])


    # async def _process_tool_results(self, tool_results: List[ToolCallResultContent]) -> AsyncGenerator[ModelMessage, None]:
    #     """ Process the results of tool calls. """
    #     logger.info(f"Processing {len(tool_results)} tool results.")
    #     for tool_result in tool_results:
    #         logger.info(f"Tool result: {tool_result.name} with args {tool_result.arguments} returned {tool_result.result}")
    #     yield ModelMessage(role="assistant", content=[TextContent(text=f"Processed {len(tool_results)} tool results.")])

    async def _finalize(self) -> AsyncGenerator[ModelMessage, None]:
        """Finalize the response after processing tool results. This can be used to trigger follow-up actions, e.g. by asking the LLM for the next step based on the tool results."""
        logger.info(f"Finalizing response after processing tool results.")
        yield ModelMessage(role="assistant", content=[TextContent(text=f"Finalized response after processing tool results.")])


    async def request_tool_execution(self, tool_name: str, arguments: dict, call_id: str) -> bool:
        """
        This method can be overridden to implement custom logic for approving or rejecting tool execution requests.
        By default, it approves all tool execution requests.
        """
        if self._hidl:
            return await self._hidl.request_tool_execution(tool_name, arguments, call_id)
        return True

    def _build_system_prompt(self) -> list[str]:
        """
        Build the full system prompt for the wizard, including the base system prompt and any additional information from loaded skills.
        """
        system_prompts = [self.system_prompt]
        skills_prompts = self._build_skills_prompt()
        system_prompts.extend(skills_prompts)
        return system_prompts

    def _build_skills_prompt(self) -> list[str]:
        """
        Returns a combined prompt for all loaded skills that can be included in the system prompt
        to provide the wizard with information about its skills and how to use them.
        :return:
        """
        skills_prompts = []
        if not self._skill_registry or len(self._skill_registry.list_skill_names()) == 0:
            return skills_prompts
        for skill_name in self._skill_registry.list_skill_names():
            skill = self._skill_registry.get_skill(skill_name)
            if skill:
                skills_prompt = f"You have a special skill named {skill_name}:\n"
                skills_prompt += f"{skill.description}\n"
                skills_prompt += f"Instructions for {skill_name} are following:\n{skill.instructions}\n\n"
                skills_prompts.append(skills_prompt)
        return skills_prompts

    def load_skill(self, skill_name: str):
        """
        Load a skill by name and add its tools to the wizard's available tools.
        """
        logger.warning(f"Using deprecated method Wizard.load_skill(). Use 'Wizard.skills.load({skill_name})' instead.")
        self._skill_registry.load_skill(skill_name)

    def unload_skill(self, skill_name: str):
        """
        Unload a skill by name.
        """
        logger.warning(f"Using deprecated method Wizard.unload_skill(). Use 'Wizard.skills.unload({skill_name})' instead.")
        self._skill_registry.unload_skill(skill_name)


class CliWizard(Wizard):

    async def request_tool_execution(self, tool_name: str, arguments: dict, call_id: int) -> bool:
        asyncio.create_task(asyncio.to_thread(
            tts_say_cli(f"A tool call was requested: {tool_name} with {len(arguments)} arguments. Do you approve?")))

        user_input = input(f"Tool '{tool_name}' wants to execute with arguments {arguments}. Approve? (y/n): ")
        return user_input.lower() == 'y'



class WizardConfig(pydantic.BaseModel):
    """
    BotConfig represents the configuration for a wizard, including its name, model, system prompt, description, tools, and skills.
    This can be used to define wizards in JSON files and load them into Wizard instances.
    """
    name: str
    model: str
    system: str
    label: str | None = None
    description: str | None = None
    tools: list[str] | None = pydantic.Field(default_factory=list)
    mcp_servers: dict[str, dict] | None = pydantic.Field(default_factory=dict)
    skills: list[str] | None = pydantic.Field(default_factory=list)



def init_wizard_by_name(name: str, file_path: str = None) -> Wizard:
    """
    Load a wizard configuration from a JSON file and create a Wizard instance.
    The JSON file should contain the following fields:
    - name: The name of the wizard
    - model: (optional) The AI model to use for this wizard
    - system: (optional) The system prompt to use for this wizard
    - description: (optional) A description of the wizard's purpose and capabilities
    - tools: (optional) A list of tool definitions that the wizard can use
    - mcp_servers: (optional) A dictionary of MCP server configurations that the wizard can connect to
    """
    if file_path is None:
        file_path = f"{DATA_DIR}/wizards.json"

    data = read_json(file_path)
    if not isinstance(data, list):
        raise ValueError(f"Invalid wizard configuration in {file_path}: expected a JSON list of BotConfig data.")

    config = next((item for item in data if item.get("name") == name), None)
    if config is None:
        raise ValueError(f"Wizard configuration with name '{name}' not found in {file_path}.")

    try:
        botconf = WizardConfig.model_validate(config)
    except pydantic.ValidationError as e:
        raise ValueError(f"Invalid wizard configuration in {file_path}: {str(e)}")
    return init_wizard(botconf)


def init_wizard(botconf: WizardConfig) -> Wizard:
    tool_registry = ToolRegistry()
    init_builtin_tools(tool_registry)
    #for tool in tools:
    #    tool_registry.allow_tool(tool)
    #for mcp_server_id, mcp_server_config in mcp_servers.items():
    #    tool_registry.register_mcp_server(mcp_server_id, mcp_server_config)
    skill_registry = SkillRegistry()
    for skill in botconf.skills:
        skill_registry.load_skill(skill)

    system_prompt = botconf.system or DEFAULT_WIZARD_SYSTEM_PROMPT
    # if an INSTRUCTIONS.md exist in wizard's directory, we can append it to the system prompt
    wizard_dir = f"{DATA_DIR}/wizards/{botconf.name}"
    instructions_path = f"{wizard_dir}/INSTRUCTIONS.md"
    if os.path.exists(instructions_path):
        with open(instructions_path, "r") as f:
            instructions = f.read()
            system_prompt += f"\n\n{instructions}"

    wizard = Wizard(name=botconf.name, description=botconf.description,
                    model=botconf.model, system_prompt=system_prompt,
                    tool_registry=tool_registry, skill_registry=skill_registry)
    return wizard



class WizardRegistry:
    def __init__(self, config_path: str = None, auto_load: bool = True):
        self._wizard_configs: dict[str, WizardConfig] = {}
        self._wizards: dict[str, Wizard] = {}
        self._config_path = config_path or f"{DATA_DIR}/wizards.json"
        if auto_load:
            self.from_config_file()

    def get_config(self, name) -> WizardConfig | None:
        """Get the configuration for a wizard by name. Returns None if no configuration is found."""
        return self._wizard_configs.get(name)

    def get_instance(self, name) -> Wizard | None:
        """Get a Wizard instance by name. If the wizard is not already loaded, it will be initialized from its configuration if available. Returns None if no wizard instance can be found or initialized."""
        if name in self._wizards:
            return self._wizards[name]
        elif name in self._wizard_configs:
            try:
                wizard = init_wizard(self._wizard_configs[name])
                self._register_wizard(wizard)
                return wizard
            except Exception as e:
                logger.error(f"Error initializing wizard '{name}': {str(e)}", exc_info=e)
                return None
        return self._wizards.get(name)

    def list_configured(self) -> set[str]:
        """Names of configured wizards"""
        return set(self._wizard_configs.keys())

    def list_loaded(self) -> set[str]:
        """Names of currently loaded wizards"""
        return set(self._wizards.keys())

    def unload_wizard(self, name: str) -> None:
        """Unload a wizard by name. This removes the wizard instance from the registry but keeps its configuration available for future loading. If the wizard is not currently loaded, this method does nothing."""
        if name in self._wizards:
            del self._wizards[name]
            logger.info(f"Wizard '{name}' unloaded.")
        else:
            logger.warning(f"Attempted to unload wizard '{name}' which is not currently loaded.")

    def _register_wizard(self, wizard: Wizard):
        """Internal method"""
        if not wizard or not isinstance(wizard, Wizard):
            raise ValueError("Invalid wizard object provided for registration.")
        if wizard.name in self._wizards:
            raise ValueError(f"Wizard with name '{wizard.name}' is already registered.")
        self._wizards[wizard.name] = wizard
        logger.info(f"Wizard '{wizard.name}' registered.")

    def from_config_file(self):
        if os.path.exists(self._config_path):
            data = read_json(self._config_path)
            if not isinstance(data, list):
                raise ValueError(f"Invalid wizard configuration in {self._config_path}: expected a JSON list of BotConfig data.")
            for config in data:
                try:
                    botconf = WizardConfig.model_validate(config)
                    #wizard = init_wizard(botconf)
                    #self.register_wizard(wizard)
                    #logger.info(f"Loaded wizard '{wizard.name}' from config.")
                    self._wizard_configs[botconf.name] = botconf
                    logger.info(f"Wizard '{botconf.name}' registered.")
                except Exception as e:
                    logger.error(f"Error loading wizard from config: {str(e)}", exc_info=e)
        else:
            logger.warning(f"Wizard configuration file not found at {self._config_path}. No wizards loaded.")



# def get_chat_memory(username: str, assistant_name: str, conversation_id: str, create=False) -> ChatMemory:
#     # using a file based chat memory for simplicity
#     file_path = f"{DATA_DIR}/chats/{username}/{assistant_name}/{conversation_id}/memory.json"
#     print(f"Loading chat memory from {file_path}", create)
#     return FileChatMemory(file_path, create=create)
#
