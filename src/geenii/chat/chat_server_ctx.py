import asyncio
import os

from fastapi import FastAPI

from geenii.chat.chat_manager import ChatManager
from geenii.chat.chat_server_core import ConnectionManager, MessageHandler, logger
from geenii.chat.chat_server_ext_discord import DiscordBotConnector


class ChatServerState:

    def __init__(self, app: FastAPI):
        self.chat_manager: ChatManager | None = None
        self.conn_manager: ConnectionManager | None = None
        self.message_handler: MessageHandler | None = None
        self.in_queue: asyncio.Queue = asyncio.Queue()
        self.out_queue: asyncio.Queue = asyncio.Queue()

        self._message_handler_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()

    async def startup(self) -> None:
        chat_manager = ChatManager()
        chat_manager.init_db()

        conn_manager = ConnectionManager()

        DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
        # TARGET_USER_ID = 123456789012345678  # replace with the user's ID (int)
        if DISCORD_BOT_TOKEN:
            logger.info("DETECTED DISCORD_BOT_TOKEN, starting Discord bot connector ...")
            await DiscordBotConnector(token=DISCORD_BOT_TOKEN,
                                      conns=conn_manager,
                                      chat_manager=chat_manager,
                                      queue=self.in_queue,
                                      shutdown_event=self._shutdown_event).start()

        # if SLACK_BOT_TOKEN and SLACK_CHANNEL_ID:
        #    logger.info("DETECTED SLACK_BOT_TOKEN, starting Discord bot connector ...")
        #   SlackConnector(in=in_queue, token="your_slack_bot_token", channel_id="slack_channel_id").start()

        msg_handler = MessageHandler(inbound=self.in_queue, outbound=self.out_queue,
                                     chat_manager=chat_manager, conns=conn_manager,
                                     shutdown_event=self._shutdown_event, )
        asyncio.create_task(msg_handler.run())

        self.chat_manager = chat_manager
        self.conn_manager = conn_manager
        self.message_handler = msg_handler

    async def stop(self) -> None:
        self._shutdown_event.set()
        await self.conn_manager.close()
        # await self.message_handler.stop()
        # self._message_handler_task.cancel()
        self.chat_manager.close()
