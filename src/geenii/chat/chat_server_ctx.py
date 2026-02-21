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

        self._app = app
        self._message_handler_task: asyncio.Task | None = None
        self._shutdown_event = asyncio.Event()
        self._connectors = []

    async def startup(self) -> None:
        chat_manager = ChatManager()
        conn_manager = ConnectionManager()

        msg_handler = MessageHandler(inbound=self.in_queue, outbound=self.out_queue,
                                     chat_manager=chat_manager,
                                     conns=conn_manager,
                                     shutdown_event=self._shutdown_event, )
        await msg_handler.start()

        # WebSocket connector
        # ws_connector = WebSocketConnector(conns=conn_manager, chat_mgr=chat_manager, msg_handler=msg_handler, app=self._app)
        # await ws_connector.start()
        # self._connectors.append(ws_connector)

        # Discord bot connector if token is provided
        DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN")
        # TARGET_USER_ID = 123456789012345678  # replace with the user's ID (int)
        if DISCORD_BOT_TOKEN:
            logger.info("DETECTED DISCORD_BOT_TOKEN, starting Discord bot connector ...")
            discord_connector = DiscordBotConnector(token=DISCORD_BOT_TOKEN,
                                                    conns=conn_manager,
                                                    chat_manager=chat_manager,
                                                    queue=self.in_queue,
                                                    shutdown_event=self._shutdown_event)
            await discord_connector.start()
            self._connectors.append(discord_connector)

        self.chat_manager = chat_manager
        self.conn_manager = conn_manager
        self.message_handler = msg_handler

    async def stop(self) -> None:
        self._shutdown_event.set()
        await self.conn_manager.shutdown()
        await self.message_handler.shutdown()
        self.chat_manager.close()
