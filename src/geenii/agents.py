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

DEFAULT_AGENT_SYSTEM_PROMPT = """
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
    Base class for a task in the agent's process.
    A task represents a unit of work that can be executed asynchronously and can yield messages as it runs.
    """

    @abc.abstractmethod
    async def execute(self) -> AsyncGenerator[Any, None]:
        """
        The run method should be implemented by subclasses to perform the task's work and yield messages or other content as needed.
        """
        yield ModelMessage(role="assistant", content=[TextContent(text=f"Not implemented.")])


class BaseAgentTask(BaseTask, abc.ABC):
    """
    Base class for a agent task.
    The agent tasks has a reference to the agent instance and can access its tools, skills, memory, etc. to perform its work.
    """

    def __init__(self, agent: "BaseAgent"):
        self.agent = agent


class LLMTask(BaseAgentTask):
    """Generate LLM chat completion response in the current context. Handles tool calls"""

    def __init__(self, agent: "BaseAgent", message: str | list[ContentPart], allowed_tools: Set[str] | None = None):
        super().__init__(agent)
        self.message = message
        self.allowed_tools = allowed_tools
        if self.allowed_tools is None:
            self.allowed_tools = set(self.agent.allowed_tools)

    async def execute(self) -> AsyncGenerator[ModelMessage, None]:
        full_system_prompt = self._build_system_prompt()
        # print(full_system_prompt)
        prompt = message_to_prompt(self.message)
        # allowed_tools = set(self._tool_registry.list_tool_names())
        # allowed_tools = self.agent.allowed_tools.intersection(set(self.agent.tools.list_tool_names()))
        allowed_tools = self.allowed_tools
        input_messages = list(
            self.agent.message_history[-10:])  # snapshot of the current message history (last 10 messages)

        # run sync task in thread pool to avoid blocking the event loop while waiting for the response
        request = ChatCompletionRequest(prompt=prompt,
                                        model=self.agent.model,
                                        system=full_system_prompt,
                                        messages=input_messages,  # snapshot of the current message history
                                        tools=allowed_tools,
                                        context_id=self.agent.context_id
                                        )
        response = await asyncio.to_thread(self._request_completion, request)
        logger.info(f"Received model response for prompt '{prompt}' with {len(response.output)} content parts.")

        # add user request to message history
        user_message = ModelMessage(role="user", content=[TextContent(text=prompt)])
        self.agent.message_history.append(user_message)

        # add model response to message history
        bot_message = ModelMessage(role="assistant", content=response.output)
        self.agent.message_history.append(bot_message)

        # yield the output message
        yield bot_message

        tool_calls = 0
        for item in response.output:
            # handle tool calls
            if isinstance(item, ToolCallContent):
                tool_calls += 1
                # enqueue tool call for processing and yield a placeholder message until the tool result is available
                await self.agent.enqueue_task(
                    ToolCallTask(self.agent, tool_name=item.name, arguments=item.arguments, call_id=item.call_id))

        # if there were tool calls, we can optionally trigger a follow-up action,
        # e.g. by enqueuing another task to process the tool results or to ask the LLM for the next step based on the tool results.
        if tool_calls > 0:
            logger.info(
                f"{tool_calls} tool calls were made in the response. Enqueuing follow-up task to process tool results.")
            await self.agent.enqueue_task(FinalizeTask(self.agent))

    def _request_completion(self, request):
        response = generate_chat_completion(request=request, tool_registry=self.agent.tools, )
        return response

    def _build_system_prompt(self) -> list[str]:
        """
        Build the full system prompt for the agent, including the base system prompt and any additional information from loaded skills.
        """
        system_prompts = [self.agent.system_prompt]
        skills_prompts = self._build_skills_prompt()
        system_prompts.extend(skills_prompts)
        return system_prompts

    def _build_skills_prompt(self) -> list[str]:
        """
        Returns a combined prompt for all loaded skills that can be included in the system prompt
        to provide the agent with information about its skills and how to use them.
        :return:
        """
        skills_prompts = []
        if not self.agent.skills or len(self.agent.skills.list_skill_names()) == 0:
            return skills_prompts
        for skill_name in self.agent.skills.list_skill_names():
            skill = self.agent.skills.get_skill(skill_name)
            if skill:
                skills_prompt = f"You have a special skill named {skill_name}:\n"
                skills_prompt += f"{skill.description}\n"
                skills_prompt += f"Instructions for {skill_name} are following:\n{skill.instructions}\n\n"
                skills_prompts.append(skills_prompt)
        return skills_prompts


class FinalizeTask(BaseAgentTask):
    def __init__(self, agent: "BaseAgent"):
        super().__init__(agent)

    async def execute(self) -> AsyncGenerator[ModelMessage | BaseTask, None]:
        yield ModelMessage(role="assistant",
                           content=[TextContent(text=f"Finalizing response after processing tool results.")])

        yield LLMTask(self.agent, message="Based on the previous outputs generate a final response",
                      allowed_tools=set())


class ToolCallTask(BaseAgentTask):
    def __init__(self, agent: "BaseAgent", tool_name: str, arguments: dict, call_id: str = None):
        super().__init__(agent)
        self.tool_name = tool_name
        self.arguments = arguments
        self.call_id = call_id

    async def execute(self) -> AsyncGenerator[ModelMessage, None]:
        tool_name = self.tool_name
        arguments = self.arguments
        call_id = self.call_id
        tool_usage_approved = await self.agent.request_tool_execution(tool_name=tool_name, arguments=arguments,
                                                                      call_id=call_id)
        if not tool_usage_approved:
            logger.critical(f"Tool execution for {tool_name} was rejected by the request_tool_execution method.")
            tool_result = {"error": "Tool execution rejected."}
            msg = ModelMessage(role="tool", content=[
                ToolCallResultContent(name=tool_name, arguments=arguments, result=tool_result, call_id=call_id)])
            yield msg
            self.agent.message_history.append(msg)
            return

        logger.info(f"Calling tool {tool_name} with arguments {arguments}")
        try:
            tool_result = await execute_tool_call(self.agent.tools, tool_name, **arguments)
            logger.info(f"Tool {tool_name} returned result: {tool_result}")
        except Exception as e:
            logger.exception(f"Error executing tool {tool_name}", exc_info=e)
            tool_result = {"error": str(e)}
        msg = ModelMessage(role="tool", content=[
            ToolCallResultContent(name=tool_name, arguments=arguments, result=tool_result, call_id=call_id)])
        yield msg
        self.agent.message_history.append(msg)


class ToolFilterTask(BaseAgentTask):
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

    def __init__(self, agent: "BaseAgent", prompt: str, tool_registry: ToolRegistry):
        super().__init__(agent)
        self.prompt = prompt
        self.tool_registry = tool_registry

    async def execute(self) -> AsyncGenerator[ModelMessage, None]:

        tools_str = "\n".join([f"- {tool_name}: {self.tool_registry.get_tool_description(tool_name)}" for tool_name in
                               self.tool_registry.list_tool_names()])

        request = ChatCompletionRequest(
            model=self.agent.model,
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
                    logger.info(
                        f"Tool filter selected tools: {selected_tools} with confidence {parsed.get('confidence', 'N/A')}")
            if isinstance(response.output[0], TextContent):
                parsed = parse_json_safe(response.output[0].text)
                if parsed and "tools" in parsed and isinstance(parsed["tools"], list):
                    selected_tools = parsed["tools"]
                    logger.info(
                        f"Tool filter selected tools: {selected_tools} with confidence {parsed.get('confidence', 'N/A')}")

        # now update the agent's tool registry to only allow the selected tools for the next LLM response
        # self.agent.set_allowed_tools(selected_tools)
        # yield WizModMessage(self.agent, allowed_tools=selected_tools)

        # yield a no-op message just to trigger the next step in the process
        yield ModelMessage(role="assistant", content=[TextContent(text=f"Selected tools: {', '.join(selected_tools)}")])


# class AnonymousTask(BaseTask):
#     def __init__(self, fn: Callable[[], AsyncGenerator[ModelMessage, None]]):
#         self.fn = fn
#
#     async def run(self) -> AsyncGenerator[ModelMessage, None]:
#         async for msg in self.fn():
#             yield msg


class HandoffTask(BaseAgentTask):
    """Task to hand off the conversation to another agent or agent"""

    def __init__(self, agent: "BaseAgent", target_agent_name: str, prompt: str = None):
        super().__init__(agent)
        self.target_agent_name = target_agent_name
        self.prompt = prompt or f"Handing off the conversation to {target_agent_name}."

        sub = init_agent_by_name(target_agent_name)
        if not sub:
            raise ValueError(f"Target agent '{target_agent_name}' not found for handoff.")
        self.sub = sub
        self.sub._hidl = self.agent._hidl  # share the same human-in-the-loop handler

    async def execute(self) -> AsyncGenerator[ModelMessage, None]:
        # This is a placeholder implementation. In a real implementation, you would look up the target agent by name,
        # transfer the conversation context and message history to the target agent, and yield a message indicating the handoff.
        msg = ModelMessage(role="assistant",
                           content=[TextContent(text=f"Handing off conversation to {self.target_agent_name}.")])
        self.agent.message_history.append(msg)

        # todo transfer conversation context and message history
        #self.sub.message_history.extend(list(self.agent.message_history[-6:]))  # transfer last 6 messages as context

        async for msg in self.sub.prompt(self.prompt):
            yield msg


class FindBestAgentTask(BaseAgentTask):
    """Find the best-suitable agent to handle the current conversation based on the current message and context"""

    SYSTEM_PROMPT = """
    You are an AI agent selector. Given a user prompt and conversation context, you must:
    1. Select the best-fit agent from the provided list.
    2. Provide a brief rationale for your choice.
    
    The list includes a brief description of each agent's capabilities and purpose to help you make an informed decision.
    Format:
    - <agent_name>: <brief description of the agent's purpose>

    Rules:
    - Always select the agent that is best suited to handle the user's request based on its capabilities and the conversation context.
    - Only produce a final answer with the selected agent's name and rationale. Do not list multiple agents or provide any other information.

    Always respond with valid JSON in exactly this shape:
    {
      "agent":       "<agent_name>",
      "confidence":   <0.0-1.0>,
      "rationale":    "<brief explanation of why this agent is the best fit>"
    }

    If no agent fits well, pick the closest option or 'NONE' and lower the confidence score.
    """.strip()

    OUTPUT_SCHEMA = {
        "type": "object",
        "properties": {
            "agent": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
            "rationale": {"type": "string"}
        },
        "required": ["agent", "confidence", "rationale"],
        "additionalProperties": False
    }

    def __init__(self, agent: "BaseAgent", prompt: str):
        super().__init__(agent)
        self.prompt = prompt
        self.agent_registry = init_agent_registry(auto_load=True)

    async def execute(self) -> AsyncGenerator[ModelMessage | BaseTask, None]:
        available_agents = []
        for agent in self.agent_registry._agent_configs.values():
            description = agent.description or "No description available."
            tools = ",".join(agent.tools) if agent.tools else "No tools"
            skills = ",".join(agent.skills) if agent.skills else "No special skills"
            agent_info = f"{agent.name}: {description} using {tools}"
            available_agents.append(agent_info)
        agents_str = "\n - ".join(available_agents)

        request = ChatCompletionRequest(
            model=self.agent.model,
            model_parameters={"temperature": 0.1, "max_tokens": 512},
            system=[self.SYSTEM_PROMPT, f"Available agents:\n{agents_str}"],
            prompt=self.prompt,
            messages=[],
            output_format="json",
            output_schema=self.OUTPUT_SCHEMA,
        )
        response = await asyncio.to_thread(generate_chat_completion, request)
        logger.info(f"Received model response for agent selection with {len(response.output)} content parts.")
        selected_agent = None
        if len(response.output) > 0:
            parsed = None
            if isinstance(response.output[0], JsonContent):
                parsed = response.output[0].data
            if isinstance(response.output[0], TextContent):
                parsed = parse_json_safe(response.output[0].text)

            logger.info(parsed)
            if parsed and "agent" in parsed and isinstance(parsed["agent"], str):
                selected_agent = parsed["agent"]
                logger.info(
                    f"Agent selector selected agent: {selected_agent} with confidence {parsed.get('confidence', 'N/A')}. Rationale: {parsed.get('rationale', 'N/A')}")

        if selected_agent:
            yield ModelMessage(role="assistant", content=[TextContent(
                text=f"Selected agent: {selected_agent} with confidence {parsed.get('confidence', 'N/A')}. Rationale: {parsed.get('rationale', 'N/A')}")])
            yield HandoffTask(self.agent, target_agent_name=selected_agent, prompt=self.prompt)

        else:
            yield ModelMessage(role="assistant", content=[TextContent(text=f"No suitable agent found.")])


class HumanInTheLoopHandler:
    """
    This class can be used to handle human-in-the-loop interactions for tool call approvals or other decision points in the agent's process.
    """

    async def request_tool_execution(self, tool_name: str, arguments: dict, call_id: str) -> bool:
        """
        This method can be overridden to implement custom logic for approving or rejecting tool execution requests.
        By default, it approves all tool execution requests.
        """
        return True


class BaseAgent(BotInterface, abc.ABC):
    MAX_TASKS = 10  # maximum number of tasks to process in the queue to prevent infinite loops

    def __init__(self, name, model: str = None, system_prompt: str = None, description: str = None,
                 tool_registry: ToolRegistry = None, skill_registry: SkillRegistry = None,
                 allowed_tools: Set[str] = None,
                 context_id: str = None, memory: ChatMemory = None, hidl: HumanInTheLoopHandler = None):

        self.name = name
        self.description = description
        self.model = model or DEFAULT_COMPLETION_MODEL
        self.system_prompt = system_prompt or DEFAULT_AGENT_SYSTEM_PROMPT
        self.message_history: List[ModelMessage] = []
        self.memory = memory or None
        self.context_id = context_id or None
        self.allowed_tools: Set[str] = allowed_tools or set()

        self._tool_registry = tool_registry or ToolRegistry()
        self._skill_registry = skill_registry or SkillRegistry()
        self._tasks: asyncio.Queue[BaseTask] = asyncio.Queue()
        self._hidl = hidl or HumanInTheLoopHandler()

    def __repr__(self):
        return f"Agent(name={self.name}, context_id={self.context_id}, model={self.model}, tools={self.allowed_tools}, skills={self.skills.list_skill_names()})"

    @property
    def tools(self) -> ToolRegistry:
        return self._tool_registry

    @property
    def skills(self) -> SkillRegistry:
        return self._skill_registry

    async def enqueue_task(self, task: BaseTask):
        """Enqueue a task to be processed by the agent."""
        await self._tasks.put(task)

    async def prompt(self, message: str | list[ContentPart]) -> AsyncGenerator[ModelMessage, None]:
        """Process an incoming message and generate a response by enqueuing tasks to the internal queue and processing them sequentially."""
        # enqueue new llm task
        # await self._tasks.put(LLMTask(self, message=message))
        # await self._tasks.put(FindBestAgentTask(self, prompt=message_to_prompt(message)))
        await self._handle_prompt(message)

        # process the queue and yield messages
        async for msg in self._process_queue():
            yield msg

    @abc.abstractmethod
    async def _handle_prompt(self, message: str | list[ContentPart]):
        """Handle an incoming prompt message by enqueuing an LLM task to generate a response."""
        # await self.enqueue_task(LLMTask(self, message=message))
        ...

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
        Load a skill by name and add its tools to the agent's available tools.
        """
        logger.warning(f"Using deprecated method Agent.load_skill(). Use 'Agent.skills.load({skill_name})' instead.")
        self.skills.load_skill(skill_name)

    def unload_skill(self, skill_name: str):
        """
        Unload a skill by name.
        """
        logger.warning(
            f"Using deprecated method Agent.unload_skill(). Use 'Agent.skills.unload({skill_name})' instead.")
        self.skills.unload_skill(skill_name)


class Agent(BaseAgent):
    async def _handle_prompt(self, message: str | list[ContentPart]):
        await self.enqueue_task(LLMTask(self, message=message))


class RoutingAgent(BaseAgent):
    async def _handle_prompt(self, message: str | list[ContentPart]):
        await self.enqueue_task(FindBestAgentTask(self, prompt=message_to_prompt(message)))


class CliAgent(Agent):

    async def request_tool_execution(self, tool_name: str, arguments: dict, call_id: int) -> bool:
        asyncio.create_task(asyncio.to_thread(
            tts_say_cli(f"A tool call was requested: {tool_name} with {len(arguments)} arguments. Do you approve?")))

        user_input = input(f"Tool '{tool_name}' wants to execute with arguments {arguments}. Approve? (y/n): ")
        return user_input.lower() == 'y'


class AgentConfig(pydantic.BaseModel):
    """
    BotConfig represents the configuration for a agent, including its name, model, system prompt, description, tools, and skills.
    This can be used to define agents in JSON files and load them into Agent instances.
    """
    name: str
    model: str
    system: str
    label: str | None = None
    description: str | None = None
    tools: list[str] | None = pydantic.Field(default_factory=list)
    mcp_servers: dict[str, dict] | None = pydantic.Field(default_factory=dict)
    skills: list[str] | None = pydantic.Field(default_factory=list)
    model_parameters: dict | None = pydantic.Field(default_factory=dict)


def init_agent_by_name(name: str, file_path: str = None) -> Agent:
    """
    Load a agent configuration from a JSON file and create a Agent instance.
    The JSON file should contain the following fields:
    - name: The name of the agent
    - model: (optional) The AI model to use for this agent
    - system: (optional) The system prompt to use for this agent
    - description: (optional) A description of the agent's purpose and capabilities
    - tools: (optional) A list of tool definitions that the agent can use
    - mcp_servers: (optional) A dictionary of MCP server configurations that the agent can connect to
    """
    if file_path is None:
        file_path = f"{DATA_DIR}/agents.json"

    data = read_json(file_path)
    if not isinstance(data, list):
        raise ValueError(f"Invalid agent configuration in {file_path}: expected a JSON list of BotConfig data.")

    config = next((item for item in data if item.get("name") == name), None)
    if config is None:
        raise ValueError(f"Agent configuration with name '{name}' not found in {file_path}.")

    try:
        botconf = AgentConfig.model_validate(config)
    except pydantic.ValidationError as e:
        raise ValueError(f"Invalid agent configuration in {file_path}: {str(e)}")
    return init_agent(botconf)


def init_agent(botconf: AgentConfig) -> Agent:
    tool_registry = ToolRegistry()
    init_builtin_tools(tool_registry)
    # for tool in tools:
    #    tool_registry.allow_tool(tool)
    # for mcp_server_id, mcp_server_config in mcp_servers.items():
    #    tool_registry.register_mcp_server(mcp_server_id, mcp_server_config)
    skill_registry = SkillRegistry()
    for skill in botconf.skills:
        skill_registry.load_skill(skill)

    system_prompt = botconf.system or DEFAULT_AGENT_SYSTEM_PROMPT
    # if an INSTRUCTIONS.md exist in agent's directory, we can append it to the system prompt
    agent_dir = f"{DATA_DIR}/agents/{botconf.name}"
    instructions_path = f"{agent_dir}/INSTRUCTIONS.md"
    if os.path.exists(instructions_path):
        with open(instructions_path, "r") as f:
            instructions = f.read()
            system_prompt += f"\n\n{instructions}"

    agent_class = Agent
    if botconf.name == "default":
        agent_class = RoutingAgent

    agent = agent_class(name=botconf.name, description=botconf.description,
                  model=botconf.model, system_prompt=system_prompt,
                  allowed_tools=set(botconf.tools),
                  tool_registry=tool_registry, skill_registry=skill_registry)
    return agent


class AgentRegistry:
    def __init__(self, config_path: str = None, auto_load: bool = False):
        self._agent_configs: dict[str, AgentConfig] = {}
        self._agents: dict[str, Agent] = {}
        self._config_path = config_path or f"{DATA_DIR}/agents.json"
        if auto_load:
            self.from_config_file()

    def get_config(self, name) -> AgentConfig | None:
        """Get the configuration for a agent by name. Returns None if no configuration is found."""
        return self._agent_configs.get(name)

    def get_instance(self, name) -> Agent | None:
        """Get a Agent instance by name. If the agent is not already loaded, it will be initialized from its configuration if available. Returns None if no agent instance can be found or initialized."""
        if name in self._agents:
            return self._agents[name]
        elif name in self._agent_configs:
            try:
                agent = init_agent(self._agent_configs[name])
                self._register_agent(agent)
                return agent
            except Exception as e:
                logger.error(f"Error initializing agent '{name}': {str(e)}", exc_info=e)
                return None
        return self._agents.get(name)

    def list_configured(self) -> set[str]:
        """Names of configured agents"""
        return set(self._agent_configs.keys())

    def list_loaded(self) -> set[str]:
        """Names of currently loaded agents"""
        return set(self._agents.keys())

    def unload_agent(self, name: str) -> None:
        """Unload a agent by name. This removes the agent instance from the registry but keeps its configuration available for future loading. If the agent is not currently loaded, this method does nothing."""
        if name in self._agents:
            del self._agents[name]
            logger.info(f"Agent '{name}' unloaded.")
        else:
            logger.warning(f"Attempted to unload agent '{name}' which is not currently loaded.")

    def _register_agent(self, agent: Agent):
        """Internal method"""
        if not agent or not isinstance(agent, BaseAgent):
            raise ValueError("Invalid agent object provided for registration.")
        if agent.name in self._agents:
            raise ValueError(f"Agent with name '{agent.name}' is already registered.")
        self._agents[agent.name] = agent
        logger.info(f"Agent '{agent.name}' registered.")

    def from_config_file(self):
        if os.path.exists(self._config_path):
            data = read_json(self._config_path)
            if not isinstance(data, list):
                raise ValueError(
                    f"Invalid agent configuration in {self._config_path}: expected a JSON list of BotConfig data.")
            for config in data:
                try:
                    botconf = AgentConfig.model_validate(config)
                    # agent = init_agent(botconf)
                    # self.register_agent(agent)
                    # logger.info(f"Loaded agent '{agent.name}' from config.")
                    self._agent_configs[botconf.name] = botconf
                    logger.info(f"Agent '{botconf.name}' registered.")
                except Exception as e:
                    logger.error(f"Error loading agent from config: {str(e)}", exc_info=e)
        else:
            logger.warning(f"Agent configuration file not found at {self._config_path}. No agents loaded.")


def init_agent_registry(config_path: str = None, auto_load: bool = False) -> AgentRegistry:
    return AgentRegistry(config_path=config_path, auto_load=auto_load)
