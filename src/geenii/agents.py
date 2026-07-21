import logging

from geenii.agent.base_agent import BaseAgent
from geenii.agent.tasks import (
    LLMTask,
    FindBestAgentTask,
    FindBestSkillTask,
    HandoffTask,
)
from geenii.agent.base import message_to_prompt
from geenii.chat_models import ContentPart
from geenii.pm.process_manager_client import ProcessManagerClient
from geenii.tools import init_builtin_tools, init_mcp_server_tools
from geenii.core.process_tools import init_process_tools

logger = logging.getLogger(__name__)


class Agent(BaseAgent):
    """Default Agent"""

    async def _initialize(self):
        """Initialize the agent by loading built-in tools, MCP server tools, and any tools from loaded skills."""
        if self._initialized:
            return

        init_builtin_tools(self._tool_registry)
        if self.mcp_servers:
            await init_mcp_server_tools(self._tool_registry, self.mcp_servers)

        #self._tool_registry.register_function(self.about_me, name="about_me")
        #self.allowed_tools.add("about_me")

        # check if all allowed tools are available
        _allowed_tools = set()
        for tool_name in self.allowed_tools:
            if not self.tools.has(tool_name):
                logging.warning(f"Tool {tool_name} not found in tools registry")
                continue
            _allowed_tools.add(tool_name)
        self.allowed_tools = _allowed_tools

        self._initialized = True

    async def _handle_makros(self, message: str | list[ContentPart]) -> True | None:
        """
        Handle message makros.
        Following makros exist:
        - Messages starting with "@" are explicitly asking for an agent (@AGENTNAME)
        - Messages starting with "/"
        :param message:
        :return:
        """
        print("MESSAGE", message)
        if isinstance(message, str):
            if message.startswith("/"):
                message = message[1:]
                cmd, message = message.split(" ", maxsplit=1)
                print("CMD MAKRO", cmd, message)
                # enqueue command task
            elif message.startswith("@"):
                message = message[1:]
                agent_name, message = message.split(" ", maxsplit=1)
                print("AGENT MAKRO", agent_name, message)
                # enqueue a subagent
                await self.enqueue_task(HandoffTask(agent=self, target_agent_name=agent_name, prompt=message))
                return True # signal to stop message handling

        return None
    
    async def _handle_prompt(self, message: str | list[ContentPart]):
        if await self._handle_makros(message):
            return
        
        await self.enqueue_task(FindBestSkillTask(self, prompt=message_to_prompt(message)))
        await self.enqueue_task(LLMTask(self, message=message))
        #await self.enqueue_task(PlanTask(self, prompt=message_to_prompt(message)))
        #await self.enqueue_task(LLMTask(self, message="Execute the plan and call the necessary tools to complete the task."))


class RoutingAgent(Agent):
    """Routing Agent"""

    def __init__(self, name: str, **kwargs):
        super().__init__(name, **kwargs)

    async def _handle_prompt(self, message: str | list[ContentPart]):
        if await self._handle_makros(message):
            return

        await self.enqueue_task(FindBestAgentTask(self, prompt=message_to_prompt(message)))


class ProcessingAgent(Agent):
    """Processing Agent"""

    def __init__(self, name: str, pm: ProcessManagerClient = None, **kwargs):
        super().__init__(name, **kwargs)
        self._pm = pm or ProcessManagerClient()

    async def _initialize(self):
        """Initialize the agent by loading built-in tools, MCP server tools, and any tools from loaded skills."""
        if self._initialized:
            return

        init_builtin_tools(self._tool_registry)
        init_process_tools(self._tool_registry, self._pmc)
        if self.mcp_servers:
            await init_mcp_server_tools(self._tool_registry, self.mcp_servers)

        self._initialized = True