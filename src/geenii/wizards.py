import abc
import asyncio
import logging
import os
from typing import List, AsyncGenerator, Any, Set

import pydantic

from geenii.ai import generate_chat_completion
from geenii.chat.chat_bots import BotInterface
from geenii.chat.chat_models import ToolCallResultContent, ContentPart, TextContent, ToolCallContent, JsonContent
from geenii.config import DEFAULT_COMPLETION_MODEL, DATA_DIR
from geenii.datamodels import ModelMessage, ChatCompletionRequest
from geenii.memory import ChatMemory
from geenii.rt import init_builtin_tools
from geenii.skills import SkillRegistry
from geenii.tools import execute_tool_call, ToolRegistry
from geenii.tts import tts_say_cli
from geenii.utils.json_util import read_json, parse_json_safe

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


class BaseTask(abc.ABC):
    """
    Base class for a task in the wizard's process.
    A task represents a unit of work that can be executed asynchronously and can yield messages as it runs.
    """

    @abc.abstractmethod
    async def execute(self) -> AsyncGenerator[Any, None]:
        """
        The run method should be implemented by subclasses to perform the task's work and yield messages or other content as needed.
        """
        yield ModelMessage(role="assistant", content=[TextContent(text=f"Not implemented.")])


class BaseWizardTask(BaseTask, abc.ABC):
    """
    Base class for a wizard task.
    The wizard tasks has a reference to the wizard instance and can access its tools, skills, memory, etc. to perform its work.
    """

    def __init__(self, wizard: "Wizard"):
        self.wizard = wizard


class LLMTask(BaseWizardTask):
    """Generate LLM chat completion response in the current context. Handles tool calls"""
    def __init__(self, wizard: "Wizard", message: str | list[ContentPart], allowed_tools: Set[str] | None = None):
        super().__init__(wizard)
        self.message = message
        self.allowed_tools = allowed_tools
        if self.allowed_tools is None:
            self.allowed_tools = set(self.wizard.allowed_tools)

    async def execute(self) -> AsyncGenerator[ModelMessage, None]:
        full_system_prompt = self._build_system_prompt()
        # print(full_system_prompt)
        prompt = message_to_prompt(self.message)
        #allowed_tools = set(self._tool_registry.list_tool_names())
        #allowed_tools = self.wizard.allowed_tools.intersection(set(self.wizard.tools.list_tool_names()))
        allowed_tools = self.allowed_tools
        input_messages = list(self.wizard.message_history[-10:])  # snapshot of the current message history (last 10 messages)

        # run sync task in thread pool to avoid blocking the event loop while waiting for the response
        request = ChatCompletionRequest(prompt=prompt,
                                        model=self.wizard.model,
                                        system=full_system_prompt,
                                        messages=input_messages,  # snapshot of the current message history
                                        tools=allowed_tools,
                                        context_id=self.wizard.context_id
                                        )
        response = await asyncio.to_thread(self._request_completion, request)
        logger.info(f"Received model response for prompt '{prompt}' with {len(response.output)} content parts.")

        # add user request to message history
        user_message = ModelMessage(role="user", content=[TextContent(text=prompt)])
        self.wizard.message_history.append(user_message)

        # add model response to message history
        bot_message = ModelMessage(role="assistant", content=response.output)
        self.wizard.message_history.append(bot_message)

        # yield the output message
        yield bot_message

        tool_calls = 0
        for item in response.output:
            # handle tool calls
            if isinstance(item, ToolCallContent):
                tool_calls += 1
                # enqueue tool call for processing and yield a placeholder message until the tool result is available
                await self.wizard.enqueue_task(ToolCallTask(self.wizard, tool_name=item.name, arguments=item.arguments, call_id=item.call_id))

        # if there were tool calls, we can optionally trigger a follow-up action,
        # e.g. by enqueuing another task to process the tool results or to ask the LLM for the next step based on the tool results.
        if tool_calls > 0:
            logger.info(
                f"{tool_calls} tool calls were made in the response. Enqueuing follow-up task to process tool results.")
            await self.wizard.enqueue_task(FinalizeTask(self.wizard))


    def _request_completion(self, request):
        response = generate_chat_completion(request=request, tool_registry=self.wizard.tools, )
        return response

    def _build_system_prompt(self) -> list[str]:
        """
        Build the full system prompt for the wizard, including the base system prompt and any additional information from loaded skills.
        """
        system_prompts = [self.wizard.system_prompt]
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
        if not self.wizard.skills or len(self.wizard.skills.list_skill_names()) == 0:
            return skills_prompts
        for skill_name in self.wizard.skills.list_skill_names():
            skill = self.wizard.skills.get_skill(skill_name)
            if skill:
                skills_prompt = f"You have a special skill named {skill_name}:\n"
                skills_prompt += f"{skill.description}\n"
                skills_prompt += f"Instructions for {skill_name} are following:\n{skill.instructions}\n\n"
                skills_prompts.append(skills_prompt)
        return skills_prompts

class FinalizeTask(BaseWizardTask):
    def __init__(self, wizard: "Wizard"):
        super().__init__(wizard)

    async def execute(self) -> AsyncGenerator[ModelMessage|BaseTask, None]:
        yield ModelMessage(role="assistant",
                           content=[TextContent(text=f"Finalizing response after processing tool results.")])

        yield LLMTask(self.wizard, message="Based on the previous outputs generate a final response", allowed_tools=set())


class ToolCallTask(BaseWizardTask):
    def __init__(self, wizard: "Wizard", tool_name: str, arguments: dict, call_id: str = None):
        super().__init__(wizard)
        self.tool_name = tool_name
        self.arguments = arguments
        self.call_id = call_id

    async def execute(self) -> AsyncGenerator[ModelMessage, None]:
        tool_name = self.tool_name
        arguments = self.arguments
        call_id = self.call_id
        tool_usage_approved = await self.wizard.request_tool_execution(tool_name=tool_name, arguments=arguments,
                                                                       call_id=call_id)
        if not tool_usage_approved:
            logger.critical(f"Tool execution for {tool_name} was rejected by the request_tool_execution method.")
            tool_result = {"error": "Tool execution rejected."}
            msg = ModelMessage(role="tool", content=[
                ToolCallResultContent(name=tool_name, arguments=arguments, result=tool_result, call_id=call_id)])
            yield msg
            self.wizard.message_history.append(msg)
            return

        logger.info(f"Calling tool {tool_name} with arguments {arguments}")
        try:
            tool_result = execute_tool_call(self.wizard.tools, tool_name, **arguments)
            logger.info(f"Tool {tool_name} returned result: {tool_result}")
        except Exception as e:
            logger.exception(f"Error executing tool {tool_name}", exc_info=e)
            tool_result = {"error": str(e)}
        msg = ModelMessage(role="tool", content=[
            ToolCallResultContent(name=tool_name, arguments=arguments, result=tool_result, call_id=call_id)])
        yield msg
        self.wizard.message_history.append(msg)


class ToolFilterTask(BaseWizardTask):
    """Task to find the best-suitable tool to call based on the current message and context"""

    SYSTEM_PROMPT = """
    You are an AI tool orchestrator. Given a user prompt you must:
    1. Select the best-fit agent(s) from the provided list.
    2. Produce a short execution plan.

    Always respond with valid JSON in exactly this shape:
    {
      "tools":       ["<tool>", ...],
      "confidence":   <0.0-1.0>
    }

    If nothing fits well, pick the closest options and lower the confidence score.
    """.strip()

    OUTPUT_SCHEMA = {
        "type": "object",
        "properties": {
            "tools": {
                "type": "array",
                "items": {"type": "string"}
            },
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0}
        },
        "required": ["tools", "confidence"],
        "additionalProperties": False
    }

    def __init__(self, wizard: "Wizard", prompt: str, tool_registry: ToolRegistry):
        super().__init__(wizard)
        self.prompt = prompt
        self.tool_registry = tool_registry

    async def execute(self) -> AsyncGenerator[ModelMessage, None]:

        tools_str = "\n".join([f"- {tool_name}: {self.tool_registry.get_tool_description(tool_name)}" for tool_name in self.tool_registry.list_tool_names()])

        request = ChatCompletionRequest(
            model=self.wizard.model,
            model_parameters={"temperature": 0.1, "max_tokens": 512},
            system=[self.SYSTEM_PROMPT, f"Available tools:\n{tools_str}"],
            prompt=self.prompt,
            messages=[],
            output_format="json",
            output_schema=self.OUTPUT_SCHEMA,
            # tools=tool_names,
        )
        response = await asyncio.to_thread(generate_chat_completion, request)
        logger.info(f"Received model response for tool filtering with {len(response.output)} content parts.")
        selected_tools = []
        if len(response.output) > 0:
            if isinstance(response.output[0], JsonContent):
                parsed = response.output[0].data
                if parsed and "tools" in parsed and isinstance(parsed["tools"], list):
                    selected_tools = parsed["tools"]
                    logger.info(f"Tool filter selected tools: {selected_tools} with confidence {parsed.get('confidence', 'N/A')}")
            if isinstance(response.output[0], TextContent):
                parsed = parse_json_safe(response.output[0].text)
                if parsed and "tools" in parsed and isinstance(parsed["tools"], list):
                    selected_tools = parsed["tools"]
                    logger.info(f"Tool filter selected tools: {selected_tools} with confidence {parsed.get('confidence', 'N/A')}")

        # now update the wizard's tool registry to only allow the selected tools for the next LLM response
        # self.wizard.set_allowed_tools(selected_tools)
        # yield WizModMessage(self.wizard, allowed_tools=selected_tools)

        # yield a no-op message just to trigger the next step in the process
        yield ModelMessage(role="assistant", content=[TextContent(text=f"Selected tools: {', '.join(selected_tools)}")])


# class AnonymousTask(BaseTask):
#     def __init__(self, fn: Callable[[], AsyncGenerator[ModelMessage, None]]):
#         self.fn = fn
#
#     async def run(self) -> AsyncGenerator[ModelMessage, None]:
#         async for msg in self.fn():
#             yield msg


class HandoffTask(BaseWizardTask):
    """Task to hand off the conversation to another wizard or agent"""

    def __init__(self, wizard: "Wizard", target_wizard_name: str, prompt: str = None):
        super().__init__(wizard)
        self.target_wizard_name = target_wizard_name
        self.prompt = prompt or f"Handing off the conversation to {target_wizard_name}."

        sub = init_wizard_by_name(target_wizard_name)
        if not sub:
            raise ValueError(f"Target wizard '{target_wizard_name}' not found for handoff.")
        self.sub = sub

    async def execute(self) -> AsyncGenerator[ModelMessage, None]:
        # This is a placeholder implementation. In a real implementation, you would look up the target wizard by name,
        # transfer the conversation context and message history to the target wizard, and yield a message indicating the handoff.
        msg = ModelMessage(role="assistant",
                           content=[TextContent(text=f"Handing off conversation to {self.target_wizard_name}.")])
        self.wizard.message_history.append(msg)

        # todo transfer conversation context and message history
        self.sub.message_history.extend(list(self.wizard.message_history[-6:]))  # transfer last 6 messages as context

        async for msg in self.sub.prompt(self.prompt):
            yield msg



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

    MAX_TASKS = 10  # maximum number of tasks to process in the queue to prevent infinite loops

    def __init__(self, name, model: str = None, system_prompt: str = None, description: str = None,
                 tool_registry: ToolRegistry = None, skill_registry: SkillRegistry = None,
                 allowed_tools: Set[str] = None,
                 context_id: str = None, memory: ChatMemory = None, hidl: HumanInTheLoopHandler = None):

        self.name = name
        self.description = description
        self.model = model or DEFAULT_COMPLETION_MODEL
        self.system_prompt = system_prompt or DEFAULT_WIZARD_SYSTEM_PROMPT
        self.message_history: List[ModelMessage] = []
        self.memory = memory or None
        self.context_id = context_id or None
        self.allowed_tools: Set[str] = allowed_tools or set()

        self._tool_registry = tool_registry or ToolRegistry()
        self._skill_registry = skill_registry or SkillRegistry()
        self._tasks: asyncio.Queue[BaseTask] = asyncio.Queue()
        self._hidl = hidl or HumanInTheLoopHandler()

    def __repr__(self):
        return f"Wizard(name={self.name}, context_id={self.context_id}, model={self.model}, tools={self.allowed_tools}, skills={self.skills.list_skill_names()})"

    @property
    def tools(self) -> ToolRegistry:
        return self._tool_registry

    @property
    def skills(self) -> SkillRegistry:
        return self._skill_registry

    async def enqueue_task(self, task: BaseTask):
        """Enqueue a task to be processed by the wizard."""
        await self._tasks.put(task)

    async def prompt(self, message: str | list[ContentPart]) -> AsyncGenerator[ModelMessage, None]:
        """Process an incoming message and generate a response by enqueuing tasks to the internal queue and processing them sequentially."""
        # enqueue new llm task
        await self._tasks.put(LLMTask(self, message=message))

        # process the queue and yield messages
        async for msg in self._process_queue():
            yield msg

    async def _process_queue(self) -> AsyncGenerator[ModelMessage, None]:
        """
        Process tasks from the internal queue sequentially.
        Yields content parts generated by the tasks.
        Exits when the queue is empty.
        """
        i = 0
        while self._tasks.qsize() > 0 and i < self.MAX_TASKS:
            task = await self._tasks.get()
            i += 1
            logger.info(f"Task #{i} {task.__class__.__name__} started. Queue size: {self._tasks.qsize()}")
            try:
                if isinstance(task, BaseTask):
                    async for result in task.execute():
                        # parse task results
                        if result is None:
                            continue
                        if isinstance(result, ModelMessage):
                            yield result
                        elif isinstance(result, BaseTask):
                            # if the task yields another task, we enqueue it
                            await self.enqueue_task(result)
                            continue
                        else:
                            logger.critical(f"Task {task} yielded an invalid message of type {type(result)}: {result}")
                            raise ValueError(f"Unsupported task response type: {type(result)}")
                else:
                    logger.critical(f"Unsupported task type: {type(task)}")
                    raise ValueError(f"Unsupported task type: {type(task)}")
            except Exception as e:
                logger.exception(f"Error processing task {task.__class__.__name__}: {str(e)}", exc_info=e)
                # todo handle exceptions properly, e.g. by yielding an error message
                yield ModelMessage(role="assistant",
                                   content=[TextContent(text=f"An error occurred while processing the task: {str(e)}")])
            finally:
                self._tasks.task_done()

    async def request_tool_execution(self, tool_name: str, arguments: dict, call_id: str) -> bool:
        """
        This method can be overridden to implement custom logic for approving or rejecting tool execution requests.
        By default, it approves all tool execution requests.
        """
        if self._hidl:
            return await self._hidl.request_tool_execution(tool_name, arguments, call_id)
        return True


    def load_skill(self, skill_name: str):
        """
        Load a skill by name and add its tools to the wizard's available tools.
        """
        logger.warning(f"Using deprecated method Wizard.load_skill(). Use 'Wizard.skills.load({skill_name})' instead.")
        self.skills.load_skill(skill_name)

    def unload_skill(self, skill_name: str):
        """
        Unload a skill by name.
        """
        logger.warning(
            f"Using deprecated method Wizard.unload_skill(). Use 'Wizard.skills.unload({skill_name})' instead.")
        self.skills.unload_skill(skill_name)


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
    # for tool in tools:
    #    tool_registry.allow_tool(tool)
    # for mcp_server_id, mcp_server_config in mcp_servers.items():
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
                    allowed_tools=set(botconf.tools),
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
                raise ValueError(
                    f"Invalid wizard configuration in {self._config_path}: expected a JSON list of BotConfig data.")
            for config in data:
                try:
                    botconf = WizardConfig.model_validate(config)
                    # wizard = init_wizard(botconf)
                    # self.register_wizard(wizard)
                    # logger.info(f"Loaded wizard '{wizard.name}' from config.")
                    self._wizard_configs[botconf.name] = botconf
                    logger.info(f"Wizard '{botconf.name}' registered.")
                except Exception as e:
                    logger.error(f"Error loading wizard from config: {str(e)}", exc_info=e)
        else:
            logger.warning(f"Wizard configuration file not found at {self._config_path}. No wizards loaded.")
