import logging
from typing import AsyncGenerator

from geenii.bots import BotInterface
from geenii.chat_models import ChatMessage
from geenii.config import DATA_DIR
from geenii.datamodels import ModelMessage
from geenii.hidl import FileTicketHumanInTheLoopController

logger = logging.getLogger(__name__)


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