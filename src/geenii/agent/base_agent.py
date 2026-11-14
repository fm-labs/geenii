import abc
import logging
import os
import tempfile
import uuid
from collections import deque
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

import pydantic

from geenii.agent.base import DEFAULT_AGENT_SYSTEM_PROMPT, BaseTask
from geenii.bots import BotInterface
from geenii.chat_models import ContentPart, TextContent
from geenii.config import (
    DEFAULT_COMPLETION_MODEL,
    GEENII_CACHE_DIR,
    GEENII_MEMORY_ENGINE,
)
from geenii.datamodels import ModelMessage, SystemMessage, Usage
from geenii.hitl import HumanInTheLoopController, NoHumanInTheLoopController
from geenii.memory import (
    ChatMemory,
    FileChatMemory,
    ShortTermChatMemory,
    SqliteChatMemory,
)
from geenii.skills import SkillRegistry
from geenii.tool.registry import ToolRegistry
from geenii.utils.json_util import append_jsonl

logger = logging.getLogger(__name__)


class BaseAgent(BotInterface, abc.ABC):
    MAX_TASKS = 15  # maximum number of tasks to process in the queue to prevent infinite loops

    def __init__(
        self,
        name,
        model: str | None = None,
        system_prompt: str | None = None,
        developer_prompt: str | None = None,
        description: str | None = None,
        allowed_tools: set[str] | None = None,
        mcp_servers: set[str] | None = None,
        context_id: str | None = None,
        memory: ChatMemory | None = None,
        cwd: str | None = None,
        *,
        env: dict[str, str] | None = None,
        secret_keys: set[str] | None = None,
        tool_registry: ToolRegistry | None = None,
        skill_registry: SkillRegistry | None = None,
        hitl: HumanInTheLoopController | None = None,
    ):

        # configuration
        self.name = name
        self.description = description
        self.model = model or DEFAULT_COMPLETION_MODEL
        self.system_prompt = system_prompt or DEFAULT_AGENT_SYSTEM_PROMPT
        self.developer_prompt = developer_prompt or ""
        self.context_id = context_id or uuid.uuid7().hex
        self.allowed_tools: set[str] = allowed_tools or set()
        self.mcp_servers: set[str] = mcp_servers or set()
        # environment passed to tool calls (vars and secrets); never exposed in to_dict()
        self.env: dict[str, str] = env or {}
        self.secret_keys: set[str] = secret_keys or set()

        if not cwd:
            # create a temp agent dir
            self._temp_dir = tempfile.TemporaryDirectory(prefix=f"geenii_agent_{self.name}_")
            cwd = self._temp_dir.name
        self.cwd = cwd

        # runtime
        self.active_skills: list[str] = []
        # usage of all model calls made by this agent instance (and agents it handed off to), see record_usage()
        self.usage: Usage = Usage()
        self.model_calls: int = 0

        self._tool_registry = tool_registry or ToolRegistry()
        self._skill_registry = skill_registry or SkillRegistry()
        self._tasks: deque[BaseTask] = deque()
        self._hitl = hitl or NoHumanInTheLoopController()

        logger.info(f"Agent constructed with Context ID: {self.context_id}")
        self.memory = memory or self._create_memory(self.context_id)
        self._initialized = False

    def __repr__(self):
        return (
            f"Agent(name={self.name}, context_id={self.context_id}, model={self.model}, "
            f"tools={self.allowed_tools}, skills={self.skills.names()}, active_skills={self.active_skills})"
        )

    def _create_memory(self, context_id: str) -> ChatMemory:
        if GEENII_MEMORY_ENGINE == "file":
            path = os.path.join(GEENII_CACHE_DIR, "agents", self.name, f"memory.{context_id}.jsonl")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            return FileChatMemory(path)
        elif GEENII_MEMORY_ENGINE == "sqlite":
            path = os.path.join(GEENII_CACHE_DIR, "agents", self.name, f"memory.{context_id}.db")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            return SqliteChatMemory(path)
        else:
            return ShortTermChatMemory()

    def _initialize(self):
        """Initialize the agent by loading built-in tools, MCP server tools, and any tools from loaded skills."""

    def to_dict(self) -> dict:
        return {
            "context_id": self.context_id,
            "name": self.name,
            "description": self.description,
            "model": self.model,
            "system_prompt": self.system_prompt,
            "developer_prompt": self.developer_prompt,
            # "message_history": self.message_history,
            "message_count": len(self.message_history),
            "allowed_tools": list(self.allowed_tools),
            "mcp_servers": list(self.mcp_servers),
            "active_skills": list(self.active_skills),
            "hitl_class": self._hitl.__class__.__name__,
            "skills": list(self.skills.names()),
            "tools": list(self.tools.list_tool_names()),
            "usage": self.usage.model_dump(exclude_none=True),
            "model_calls": self.model_calls,
        }

    # def about_me(self):
    #     """Returns information about the agent, and it's configured tools and skills"""
    #     desc = ""
    #     desc += f"Name: {self.name}\n"
    #     desc += f"Description: {self.description}\n"
    #     desc += f"Model: {self.model}\n"
    #     desc += f"System prompt: {self.system_prompt}\n"
    #     desc += f"Developer: {self.developer_prompt}\n"
    #
    #     desc += "Available tools:\n"
    #     for tool in self.tools.list_tools():
    #         desc += f"Tool: {tool.name} - {tool.description}\n"
    #
    #     desc += "Skills:\n"
    #     for name, skill in self.skills.skills.items():
    #         desc += f"Skill: {name} - {skill.description}\n"
    #     return desc

    @property
    def tools(self) -> ToolRegistry:
        return self._tool_registry

    @property
    def skills(self) -> SkillRegistry:
        return self._skill_registry

    @property
    def hitl(self) -> HumanInTheLoopController:
        return self._hitl

    def record_usage(self, usage: Usage | None, calls: int = 1) -> None:
        """
        Count model calls and their usage. Agent tasks call this for every successful completion
        (`usage` may be None if the provider reported none); a handoff passes the sub-agent's totals.
        The counters live as long as this agent instance; they are not persisted.
        """
        self.model_calls += calls
        if usage is not None:
            self.usage = self.usage + usage

    def enqueue_task(self, task: BaseTask):
        """Enqueue a task to be processed by the agent."""
        self._tasks.append(task)

    def clear_tasks(self):
        """Drop all pending tasks, e.g. after a turn was cancelled before the queue was drained."""
        self._tasks.clear()

    def process(self, message: str | list[ContentPart]) -> Iterator[ModelMessage]:
        """Process an incoming message and generate a response by enqueuing tasks to the internal queue and processing them sequentially."""
        # lazy: runs once, after subclass __init__ has finished (subclasses may set attributes after super().__init__())
        self._initialize()
        _agent_log(self.name, self.context_id, "agent.init", self.to_dict())
        _agent_log(self.name, self.context_id, "agent.message", {"message": message})
        self._handle_message(message)

        # process the queue and yield messages
        yield from self._process_queue()

    @abc.abstractmethod
    def _handle_message(self, message: str | list[ContentPart]):
        """Handle an incoming prompt message by enqueuing an LLM task to generate a response."""
        # self.enqueue_task(LLMTask(self, message=message))
        # self.enqueue_task(FindBestAgentTask(self, prompt=message_to_prompt(message)))
        ...

    def _process_queue(self) -> Iterator[ModelMessage]:
        """
        Process tasks from the internal queue sequentially.
        Yields content parts generated by the tasks.
        Exits when the queue is empty.
        """
        i = 0
        while self._tasks:
            i += 1
            if i > self.MAX_TASKS:
                # drop remaining tasks, otherwise the loop would never terminate
                dropped = len(self._tasks)
                self._tasks.clear()
                logger.error(f"Maximum number of tasks reached: {self.MAX_TASKS}. Dropped {dropped} pending task(s).")
                _agent_log(
                    self.name,
                    self.context_id,
                    "agent.max_tasks",
                    {"max_tasks": self.MAX_TASKS, "dropped": dropped},
                )
                yield ModelMessage(
                    role="assistant",
                    content=[TextContent(text=f"Maximum number of tasks reached: {self.MAX_TASKS}")],
                )
                return

            task = self._tasks.popleft()
            try:
                logger.info(f"Task #{i}/{len(self._tasks)} {task.__class__.__name__} started.")
                _agent_log(
                    self.name,
                    self.context_id,
                    "agent.task",
                    {"i": i, "task": task.__class__.__name__},
                )
                if isinstance(task, BaseTask):
                    for result in task.execute():
                        # parse task results
                        if result is None:
                            continue
                        if isinstance(result, (ModelMessage, SystemMessage)):
                            # _agent_log(self.name, "agent.task_result", {"i": i, "task": result.__class__.__name__, "result": result})
                            _agent_log(self.name, self.context_id, "agent.task_result", result)
                            yield result
                        elif isinstance(result, BaseTask):
                            # if the task yields another task, we enqueue it
                            self.enqueue_task(result)
                            continue
                        else:
                            logger.critical(f"Task {task} yielded an invalid message of type {type(result)}: {result}")
                            raise TypeError(f"Unsupported task response type: {type(result)}")
                else:
                    logger.critical(f"Unsupported task type: {type(task)}")
                    raise TypeError(f"Unsupported task type: {type(task)}")
            except Exception as e:
                logger.exception(
                    f"Error processing task {task.__class__.__name__}: {e!s}",
                    exc_info=e,
                )
                # todo handle exceptions properly, e.g. by yielding an error message
                yield ModelMessage(
                    role="assistant",
                    content=[TextContent(text=f"An error occurred while processing the task: {e!s}")],
                )

    def request_tool_execution(self, tool_name: str, arguments: dict, call_id: str) -> bool:
        """
        This method can be overridden to implement custom logic for approving or rejecting tool execution requests.
        By default, it approves all tool execution requests.
        """
        _agent_log(
            self.name,
            self.context_id,
            "agent.request_tool_execution",
            {"tool_name": tool_name, "arguments": arguments, "call_id": call_id},
        )
        if self._hitl:
            return self._hitl.request_tool_execution(tool_name, arguments, call_id)
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
            f"Using deprecated method Agent.unload_skill(). Use 'Agent.skills.unload({skill_name})' instead."
        )
        _agent_log(self.name, self.context_id, "agent.unload_skill", {"skill_name": skill_name})
        self.skills.unload(skill_name)

    @property
    def message_history(self) -> list[ModelMessage]:
        return self.memory.messages

    def add_to_history(self, msg: ModelMessage):
        self.memory.append(msg)


def _agent_log(agent_name: str, context_id: str, event_name: str, data: dict | pydantic.BaseModel):
    date_formatted = datetime.now().strftime("%Y-%m-%d")
    # log_file = f"{CACHE_DIR}/logs/{agent_name}/logs/{agent_name}-{date_formatted}.log"
    log_file = f"{GEENII_CACHE_DIR}/logs/{agent_name}-{date_formatted}.log"
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, pydantic.BaseModel):
        data = data.model_dump(mode="json")
    append_jsonl(
        log_file,
        {
            "agent": agent_name,
            "context_id": context_id,
            "event": event_name,
            "data": data,
            "timestamp": datetime.now().timestamp(),
        },
    )


def restore_last_context_id(name: str):
    file_path = f"{GEENII_CACHE_DIR}/agents/{name}/last_context_id"
    try:
        with open(file_path, "r") as f:
            last_context_id = f.read().strip()
        if last_context_id:
            return last_context_id
    except FileNotFoundError:
        return None


def dump_last_context_id(name: str, context_id):
    file_path = f"{GEENII_CACHE_DIR}/agents/{name}/last_context_id"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        f.write(str(context_id))
