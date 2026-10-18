import logging
import shlex
import time

from geenii.agent.base import message_to_prompt
from geenii.agent.base_agent import BaseAgent
from geenii.agent.tasks import (
    LLMTask,
    FindBestAgentTask,
    FindBestSkillTask,
    HandoffTask,
    ActivateSkillTask,
    MemoryCompactionTask,
    ClearMemoryTask,
    ToolCallTask,
)
from geenii.agent.info_commands import INFO_COMMANDS, InfoCommandTask
from geenii.chat_models import ContentPart
from geenii.core.process_tools import init_process_tools
from geenii.pm.process_manager_client import ProcessManagerClient
from geenii.tools import init_mcp_server_tools

logger = logging.getLogger(__name__)


class Agent(BaseAgent):
    """Default Agent"""

    # Slash commands handled by _handle_makros; any other "/<name>" activates the skill <name>.
    BUILTIN_COMMANDS: dict[str, str] = {
        "clear": "Clear the conversation memory",
        "compact": "Summarize and compact the conversation memory",
        # read-only info commands, answered without calling the model
        **{name: description for name, (description, _) in INFO_COMMANDS.items()},
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _initialize(self):
        """Initialize the agent by loading built-in tools, MCP server tools, and any tools from loaded skills."""
        if self._initialized:
            return

        #init_builtin_tools(self._tool_registry)
        #if self.mcp_servers:
        #    init_mcp_server_tools(self._tool_registry, self.mcp_servers)

        #self._tool_registry.register_function(self.about_me, name="about_me")
        #self.allowed_tools.add("about_me")

        # check if all allowed tools are available
        _allowed_tools = set()
        for tool_name in self.allowed_tools:
            if not self.tools.has(tool_name):
                logging.warning(f"Tool {tool_name} not found in tools registry")
                #continue
            _allowed_tools.add(tool_name)
        self.allowed_tools = _allowed_tools

        self._initialized = True

    def _handle_makros(self, message: str | list[ContentPart]) -> True | None:
        """
        Handle message makros.
        Following makros exist:
        - Messages starting with "@" are explicitly asking for an agent (@AGENTNAME)
        - Messages starting with "/"
        :param message:
        :return:
        """
        logger.debug("Handling macros for message: %s", message)
        if isinstance(message, str):

            # direct agent call using '@' prefix
            # e.g. '@my-agent PROMPT'
            if message.startswith("@"):
                message = message[1:]
                parts = message.split(" ", maxsplit=1)
                agent_name = parts[0]
                message = parts[1] if len(parts) > 1 else ""
                logger.info("Agent macro: agent=%s message=%s", agent_name, message)
                # handoff to the agent
                self.enqueue_task(HandoffTask(agent=self, target_agent_name=agent_name, prompt=message))
                return True # signal to stop message handling

            # slash commands using '/' prefix
            # maps to builtin tasks or
            # fallback to skill activation
            # e.g. '/clear' (builtin task)
            if message.startswith("/"):
                message = message[1:]
                parts = message.split(" ", maxsplit=1)
                skill_name = parts[0].lower()
                prompt = parts[1] if len(parts) > 1 else ""
                logger.info("Command macro: cmd=%s message=%s", skill_name, prompt)

                if skill_name == "clear":  # keep in sync with BUILTIN_COMMANDS
                    self.enqueue_task(ClearMemoryTask(agent=self))
                    return True
                elif skill_name == "compact":
                    self.enqueue_task(MemoryCompactionTask(agent=self, prompt=prompt))
                    return True
                elif skill_name in INFO_COMMANDS:
                    self.enqueue_task(InfoCommandTask(agent=self, command=skill_name, args=prompt))
                    return True
                # elif skill_name == "memo":
                #     self.enqueue_task(StorePersistentMemoryTask(agent=self, message=prompt))
                #     return True
                # elif skill_name == "remember":
                #     self.enqueue_task(RetrievePersistentMemoryTask(agent=self, message=prompt))
                #     return True
                else:
                    self.enqueue_task(ActivateSkillTask(agent=self, skill_name=skill_name, prompt=prompt))
                    return True

            # direct tool call using ':' prefix
            if message.startswith(":"):
                parts = message.split(" ", maxsplit=1)
                tool_name = parts[0][1:]
                args_str = parts[1] if len(parts) > 1 else "" # key=value key2="value 2"
                args = {}
                try:
                    for part in shlex.split(args_str):
                        if "=" not in part:
                            raise ValueError(f"Invalid argument '{part}', expected key=value")
                        key, value = part.split("=", maxsplit=1)
                        args[key] = value
                except ValueError as e:
                    logger.warning("Tool macro: %s", e)
                    return True # signal to stop message handling

                # tool_registry: ToolRegistry = ToolRegistry()
                # init_builtin_tools(tool_registry)
                # 
                # tool = tool_registry.get(tool_name)
                # result = tool.invoke(args=args, env={})
                call_id = f"usr-{tool_name}-{time.time()}"
                self.enqueue_task(ToolCallTask(agent=self, tool_name=tool_name, arguments=args, call_id=call_id))
                return True
                

        return None
    
    def _handle_message(self, message: str | list[ContentPart]):
        if self._handle_makros(message):
            return
        
        self.enqueue_task(FindBestSkillTask(self, prompt=message_to_prompt(message)))
        self.enqueue_task(LLMTask(self, message=message))
        #self.enqueue_task(PlanTask(self, prompt=message_to_prompt(message)))
        #self.enqueue_task(LLMTask(self, message="Execute the plan and call the necessary tools to complete the task."))


class RoutingAgent(Agent):
    """Routing Agent"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def _handle_message(self, message: str | list[ContentPart]):
        if self._handle_makros(message):
            return

        self.enqueue_task(FindBestAgentTask(self, prompt=message_to_prompt(message)))


class ProcessManagerAgent(Agent):
    """Process Manager Agent"""

    def __init__(self, name: str, pm: ProcessManagerClient = None, **kwargs):
        super().__init__(name, **kwargs)
        self._pm = pm or ProcessManagerClient()

    def _initialize(self):
        """Initialize the agent by loading built-in tools, MCP server tools, and any tools from loaded skills."""
        if self._initialized:
            return

        #init_builtin_tools(self._tool_registry)
        init_process_tools(self._tool_registry, self._pm)
        if self.mcp_servers:
            init_mcp_server_tools(self._tool_registry, self.mcp_servers)

        self._initialized = True