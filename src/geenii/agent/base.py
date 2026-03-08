import abc
from typing import AsyncGenerator, Any

from geenii.chat.chat_models import TextContent, ContentPart
from geenii.datamodels import ModelMessage

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


def message_to_prompt(message: str | list[ContentPart]) -> str | None:
    if message is None:
        return None
    elif isinstance(message, str):
        return message
    elif isinstance(message, list):
        return " ".join([content.to_text() for content in message])
    else:
        raise ValueError("Unsupported message format")
