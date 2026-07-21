import os
from pathlib import Path

import abc
import asyncio
import logging
import pydantic
import uuid
from datetime import datetime
from typing import Set, List, AsyncGenerator

from geenii.agent.base import DEFAULT_AGENT_SYSTEM_PROMPT, BaseTask
from geenii.bots import BotInterface
from geenii.chat_models import ContentPart, TextContent
from geenii.config import DEFAULT_COMPLETION_MODEL, CACHE_DIR, GEENII_MEMORY_ENGINE
from geenii.datamodels import ModelMessage
from geenii.hitl import HumanInTheLoopController, NoHumanInTheLoopController
from geenii.memory import (
    ChatMemory,
    ShortTermChatMemory,
    FileChatMemory,
    SqliteChatMemory,
)
from geenii.skills import SkillRegistry
from geenii.tool.registry import ToolRegistry
from geenii.utils.json_util import append_jsonl

logger = logging.getLogger(__name__)

class BaseAgent(BotInterface, abc.ABC):
    MAX_TASKS = 15  # maximum number of tasks to process in the queue to prevent infinite loops

    def __init__(self, name, model: str = None, system_prompt: str = None, description: str = None,
                 tool_registry: ToolRegistry = None, skill_registry: SkillRegistry = None,
                 allowed_tools: Set[str] = None, mcp_servers: Set[str] = None,
                 context_id: str = None, memory: ChatMemory = None, hitl: HumanInTheLoopController = None):

        self.name = name
        self.description = description
        self.model = model or DEFAULT_COMPLETION_MODEL
        self.system_prompt = system_prompt or DEFAULT_AGENT_SYSTEM_PROMPT
        self.developer_prompt = ""
        self.context_id = context_id or uuid.uuid4().hex
        self.memory = memory or None
        self.allowed_tools: Set[str] = allowed_tools or set()
        self.mcp_servers: Set[str] = mcp_servers or set()
        self.selected_skill: str | None = None

        self._tool_registry = tool_registry or ToolRegistry()
        self._skill_registry = skill_registry or SkillRegistry()
        self._tasks: asyncio.Queue[BaseTask] = asyncio.Queue()
        self._hitl = hitl or NoHumanInTheLoopController()

        self.__init_memory()
        self._initialized = False

    def __repr__(self):
        return f"Agent(name={self.name}, context_id={self.context_id}, model={self.model}, tools={self.allowed_tools}, skills={self.skills.names()})"

    def __init_memory(self):
        if self.memory is not None:
            return
        if GEENII_MEMORY_ENGINE == "file":
            base_dir = os.path.join(CACHE_DIR, "agents", self.name, f"memory.{self.context_id}.jsonl")
            os.makedirs(os.path.dirname(base_dir), exist_ok=True)
            self.memory = FileChatMemory(base_dir)
        elif GEENII_MEMORY_ENGINE == "sqlite":
            db_path = os.path.join(CACHE_DIR, "agents", self.name, f"memory.{self.context_id}.db")
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            self.memory = SqliteChatMemory(db_path)
        else:
            self.memory = ShortTermChatMemory()


    async def _initialize(self):
        """Initialize the agent by loading built-in tools, MCP server tools, and any tools from loaded skills."""
        if self._initialized:
            return

        # init_builtin_tools(self._tool_registry)
        # init_process_tools(self._tool_registry)
        # if self.mcp_servers:
        #     await init_mcp_server_tools(self._tool_registry, self.mcp_servers)
        #
        # #self._tool_registry.register_function(self.about_me, name="about_me")
        # #self.allowed_tools.add("about_me")
        #
        # # check if all allowed tools are available
        # _allowed_tools = set()
        # for tool_name in self.allowed_tools:
        #     if not self.tools.has(tool_name):
        #         logging.warning(f"Tool {tool_name} not found in tools registry")
        #         continue
        #     _allowed_tools.add(tool_name)
        # self.allowed_tools = _allowed_tools

        self._initialized = True

    def to_dict(self) -> dict:
        return {
            "context_id": self.context_id,
            "name": self.name,
            "description": self.description,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "developer_prompt": self.developer_prompt,
            #"message_history": self.message_history,
            "message_count": len(self.message_history),
            "allowed_tools": list(self.allowed_tools),
            "mcp_servers": list(self.mcp_servers),
            "selected_skill": self.selected_skill,
            "hitl_class": self._hitl.__class__.__name__,
            "skills": list(self.skills.names()),
            "tools": list(self.tools.list_tool_names())
        }

    def about_me(self):
        """Returns information about the agent, and it's configured tools and skills"""
        desc = ""
        desc += f"Name: {self.name}\n"
        desc += f"Description: {self.description}\n"
        desc += f"Model: {self.model}\n"
        desc += f"System prompt: {self.system_prompt}\n"
        desc += f"Developer: {self.developer_prompt}\n"

        desc += "Available tools:\n"
        for tool in self.tools.list_tools():
            desc += f"Tool: {tool.name} - {tool.description}\n"

        desc += "Skills:\n"
        for skill in self.skills.skills.items():
            desc += f"Skill: {skill.name} - {skill.description}\n"
        return desc

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
        await self._initialize()
        _agent_log(self.name, self.context_id,"agent.init", self.to_dict())
        _agent_log(self.name, self.context_id, "agent.prompt", {"message": message})
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
        while self._tasks.qsize() > 0:
            i += 1
            try:
                if i >= self.MAX_TASKS:
                    raise RuntimeError(f"Maximum number of tasks reached: {self.MAX_TASKS}")

                task = await self._tasks.get()
                logger.info(
                    f"Task #{i}/{self._tasks.qsize()} {task.__class__.__name__} started."
                )
                _agent_log(self.name, self.context_id, "agent.task", {"i": i, "task": task.__class__.__name__})
                if isinstance(task, BaseTask):
                    async for result in task.execute():
                        # parse task results
                        if result is None:
                            continue
                        if isinstance(result, ModelMessage):
                            #_agent_log(self.name, "agent.task_result", {"i": i, "task": result.__class__.__name__, "result": result})
                            _agent_log(self.name, self.context_id, "agent.task_result", result)
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
        _agent_log(self.name, self.context_id, "agent.request_tool_execution",
                   {"tool_name": tool_name, "arguments": arguments, "call_id": call_id})
        if self._hitl:
            return await self._hitl.request_tool_execution(tool_name, arguments, call_id)
        return True

    def load_skill(self, skill_name: str):
        """
        Load a skill by name and add its tools to the agent's available tools.
        """
        logger.warning(f"Using deprecated method Agent.load_skill(). Use 'Agent.skills.load({skill_name})' instead.")
        _agent_log(self.name, self.context_id, "agent.load_skill", {"skill_name": skill_name})
        self.skills.load(skill_name)

    def unload_skill(self, skill_name: str):
        """
        Unload a skill by name.
        """
        logger.warning(
            f"Using deprecated method Agent.unload_skill(). Use 'Agent.skills.unload({skill_name})' instead.")
        _agent_log(self.name, self.context_id, "agent.unload_skill", {"skill_name": skill_name})
        self.skills.unload(skill_name)

    @property
    def message_history(self) -> List[ModelMessage]:
        return self.memory.messages

    def add_to_history(self, msg: ModelMessage):
        self.memory.append(msg)



def _agent_log(agent_name: str, context_id: str, event_name: str, data: dict | pydantic.BaseModel):
    date_formatted = datetime.now().strftime("%Y-%m-%d")
    #log_file = f"{CACHE_DIR}/logs/{agent_name}/logs/{agent_name}-{date_formatted}.log"
    log_file = f"{CACHE_DIR}/logs/{agent_name}-{date_formatted}.log"
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, pydantic.BaseModel):
        data = data.model_dump(mode="json")
    append_jsonl(log_file, {"agent": agent_name, "context_id": context_id, "event": event_name,
                            "data": data, "timestamp": datetime.now().timestamp()})
