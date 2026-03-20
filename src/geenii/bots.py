import abc
from typing import AsyncGenerator

from geenii.chat_models import ContentPart, TextContent
from geenii.datamodels import ModelMessage


class BotInterface(abc.ABC):
    """
    Interface for bot implementations. A bot is responsible for processing
    incoming messages, maintaining conversation state, and generating responses.
    """

    @abc.abstractmethod
    async def prompt(self, message: str | list[ContentPart]) -> AsyncGenerator[ModelMessage, None]:
        """
        Process an incoming message and generate a response.

        Args:
            message: The incoming message text or structured content parts to process

        Returns:
            An asynchronous generator that yields ContentPart objects representing the response.
        """
        yield ModelMessage(role="admin", content=[TextContent(text="Not implemented")])
