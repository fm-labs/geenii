import abc
import logging
from typing import AsyncGenerator

from geenii.chat.chat_models import TextContent, ContentPart, ChatMessage
from geenii.config import DATA_DIR
from geenii.datamodels import ModelMessage
from geenii.hidl import HumanInTheLoopController, FileTicketHumanInTheLoopController

logger = logging.getLogger(__name__)

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



class BotRunner:
    """
    A BotRunner is an ultra-thin wrapper around BotInterface and responsible for running the bot's internal logic.
    """

    def __init__(self, botname: str, room_id: str, bot: BotInterface) -> None:
        self.botname = botname
        self.room_id = room_id
        self.bot = bot
        self.bot._hidl = FileTicketHumanInTheLoopController(ticket_dir=f"{DATA_DIR}/cache/hidl")

    async def prompt(self, message: ChatMessage) -> AsyncGenerator[ModelMessage, None]:
        logger.info("Bot %s processing message in room %s: %s", self.botname, self.room_id, message)
        try:
            async for msg in self.bot.prompt(message.content):
                logger.info("Bot '%s' generated content part in room '%s': %s", self.botname, self.room_id, msg)
                yield msg
        except Exception as e:
            logger.error("Error in bot %s prompt: %s", self.botname, e)
            #yield TextContent(text=f"Error in bot response: {e}")
            #raise e