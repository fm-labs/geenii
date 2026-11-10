from __future__ import annotations

import abc
from typing import Iterator, Any, TYPE_CHECKING

if TYPE_CHECKING:
    from geenii.agent.base_agent import BaseAgent

from geenii.chat_models import TextContent, ContentPart
from geenii.datamodels import ModelMessage

DEFAULT_AGENT_SYSTEM_PROMPT = """
You are an AI assistant that MUST use available tools when they are relevant.

CORE RULES:

- NEVER answer from internal knowledge if a tool exists that can provide up-to-date, factual, or external information.
- ALWAYS evaluate whether a tool should be used BEFORE generating a final response.
- If a suitable tool exists, you MUST call the tool instead of answering directly.
- Only produce a final natural-language answer AFTER tool results are returned.
- Follow the tool calling format EXACTLY.
- Once a tool result answers the question, reply to the user. Do not call tools again.
- Never repeat a tool call with the same arguments; the earlier result is still valid.
- If a tool returns an error, try at most one fix, then explain the problem to the user.

DECISION PROCESS:

Step 1 — Analyze user intent.
Step 2 — Check available tools.
Step 3 — If any tool can help, return a tool call with the appropriate arguments.
Step 4 — If no tools are relevant, answer the user's question directly.
"""


class BaseTask(abc.ABC):
    """
    Base class for a task in the agent's process.
    A task represents a unit of work that yields messages (or follow-up tasks) as it runs.
    """

    @abc.abstractmethod
    def execute(self) -> Iterator[Any]:
        """
        The run method should be implemented by subclasses to perform the task's work and yield messages or other content as needed.
        """
        yield ModelMessage(
            role="assistant", content=[TextContent(text="Not implemented.")]
        )


class BaseAgentTask(BaseTask, abc.ABC):
    """
    Base class for a agent task.
    The agent tasks has a reference to the agent instance and can access its tools, skills, memory, etc. to perform its work.
    """

    def __init__(self, agent: "BaseAgent"):
        self.agent = agent


def message_to_prompt(message: str | list[ContentPart]) -> str | None:
    if message is None:
        return None
    elif isinstance(message, str):
        return message
    elif isinstance(message, list):
        return " ".join([content.to_text() for content in message])
    else:
        raise ValueError("Unsupported message format")
