import logging

from geenii.agent.base_agent import BaseAgent
from geenii.agent.tasks import LLMTask, FindBestAgentTask, FindBestSkillTask, PlanTask
from geenii.agent.base import message_to_prompt
from geenii.chat.chat_models import ContentPart

logger = logging.getLogger(__name__)


class Agent(BaseAgent):
    async def _handle_prompt(self, message: str | list[ContentPart]):
        await self.enqueue_task(FindBestSkillTask(self, prompt=message_to_prompt(message)))
        await self.enqueue_task(LLMTask(self, message=message))
        #await self.enqueue_task(PlanTask(self, prompt=message_to_prompt(message)))
        #await self.enqueue_task(LLMTask(self, message="Execute the plan and call the necessary tools to complete the task."))


class RoutingAgent(BaseAgent):
    async def _handle_prompt(self, message: str | list[ContentPart]):
        await self.enqueue_task(FindBestAgentTask(self, prompt=message_to_prompt(message)))
        #await self.enqueue_task(PlanTask(self, prompt=message_to_prompt(message)))



