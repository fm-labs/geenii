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

logger = logging.getLogger(__name__)


class Agent(BaseAgent):
    
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

    def __init__(self, name: str, **kwargs):
        super().__init__(name, **kwargs)

    async def _handle_prompt(self, message: str | list[ContentPart]):
        if await self._handle_makros(message):
            return

        await self.enqueue_task(FindBestAgentTask(self, prompt=message_to_prompt(message)))
