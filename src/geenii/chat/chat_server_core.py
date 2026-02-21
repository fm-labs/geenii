import asyncio
import logging
from abc import ABC, abstractmethod

from starlette.websockets import WebSocket, WebSocketState

from geenii.chat.chat_bots import BotRunner
from geenii.chat.chat_manager import ChatManager
from geenii.chat.chat_models import WireMessage, ChatMessage, ContentPart, SystemMessage, TextContent
from geenii.g import get_bot

logger = logging.getLogger(__name__)

# ---------- Connection abstractions ----------

class Connection(ABC):
    """A single participant connection that can receive broadcast messages."""

    @property
    @abstractmethod
    def username(self) -> str: ...

    @abstractmethod
    async def send(self, message: WireMessage) -> None: ...

    @abstractmethod
    async def close(self) -> None: ...


class WebSocketConnection(Connection):
    def __init__(self, username: str, websocket: WebSocket) -> None:
        self._username = username
        self._ws = websocket

    @property
    def username(self) -> str:
        return self._username

    async def send(self, message: WireMessage) -> None:
        if self._ws.client_state == WebSocketState.CONNECTED:
            await self._ws.send_json(message.model_dump())

    async def close(self) -> None:
        try:
            await self._ws.close(code=1001, reason="Server shutdown")
        except Exception:
            pass


class SseConnection(Connection):
    def __init__(self, username: str) -> None:
        self._username = username
        self.queue: asyncio.Queue = asyncio.Queue()  # queue will be consumed by the EventSourceResponse generator

    @property
    def username(self) -> str:
        return self._username

    async def send(self, message: WireMessage) -> None:
        await self.queue.put(message)

    async def close(self) -> None:
        await self.queue.put(None)  # signal to the EventSourceResponse generator to exit



class BotConnection(Connection):
    """Virtual connection for a bot participant. Instead of sending messages to an external client, we loop back"""

    def __init__(self, botname: str, room_id: str, outbox: asyncio.Queue = None) -> None:
        self._botname = botname
        self._room_id = room_id
        self._task: asyncio.Task | None = None
        self._botrunner: BotRunner | None = None

        self.inbox: asyncio.Queue = asyncio.Queue()  # internal queue for incoming messages to the bot, consumed by the bot's internal reader task
        self.outbox: asyncio.Queue = outbox  # optional queue for outgoing messages from the bot, can be consumed by an external sender task if needed

    @property
    def username(self) -> str:
        return self._botname

    @property
    def bot(self) -> BotRunner | None:
        print(f"Accessing bot runner for bot {self._botname} in room {self._room_id}")
        if self._botrunner is None:
            print("Initializing bot runner for bot %s in room %s", self._botname, self._room_id)
            g_bot = get_bot(self._botname, self._room_id)
            self._botrunner = BotRunner(botname=self._botname, room_id=self._room_id, bot=g_bot)
            print("Bot runner initialized for bot %s in room %s: %s", self._botname, self._room_id, self._botrunner)
        return self._botrunner

    async def send(self, message: WireMessage) -> None:
        # local loopback for bot messages: instead of sending to an external client,
        # we put the message into the bot's inbound queue for processing by the bot's internal logic
        if not isinstance(message, ChatMessage):
            return  # bots only process chat messages, not system notifications
        if message.sender_id == self._botname:
            return  # do not send the bot's own messages back to itself (infinite loop)

        await self.inbox.put(message)

    async def close(self) -> None:
        if self._task:
            self._task.cancel()

    def start(self) -> None:
        self._task = asyncio.create_task(self._process_message_queue())

    async def _process_message_queue(self) -> None:
        while True:
            message: ChatMessage = await self.inbox.get()

            logger.info("Bot %s received message in room %s: %s", self._botname, self._room_id, message)

            if self.bot is None:
                logger.warning("No bot logic defined for bot %s in room %s. Skipping processing.", self._botname, self._room_id)
                continue

            logger.info("Processing message with bot runner")
            async for content_part in self.bot.process(message):
                print(f"Bot {self._botname} generated content part: {content_part}")
                await self._send_to_room([content_part])

            # add some delay to simulate processing time
            logger.info("Bot %s processed message in room %s. Waiting before processing next message ...", self._botname, self._room_id)
            await asyncio.sleep(1)

    async def _send_to_room(self, content: list[ContentPart]) -> None:
        """Build a ChatMessage and put it into the outbox for broadcasting to the room."""
        message = ChatMessage(
            room_id=self._room_id,
            sender_id=self._botname,
            content=content,
        )
        if self.outbox:
            logger.info("Bot %s sending message to room %s", self._botname, self._room_id)
            await self.outbox.put(message)
        else:
            logger.warning("No outbox defined for bot %s in room %s. Message not sent: %s",
                           self._botname, self._room_id, message)


# ---------- Connection manager ----------

class ConnectionManager:
    """Maps room_id -> list[Connection] and fans out broadcasts."""

    def __init__(self) -> None:
        self.rooms: dict[str, list[Connection]] = {}

    def add(self, room_id: str, connection: Connection) -> None:
        # check if the connection already exists in the room to avoid duplicates
        existing = self.get(room_id, connection.username)
        if existing:
            logger.warning("Connection for user %s already exists in room %s. Skipping add.", connection.username,
                           room_id)
            return
        self.rooms.setdefault(room_id, []).append(connection)

    def remove(self, room_id: str, connection: Connection) -> None:
        self.rooms.get(room_id, []).remove(connection)

    def get(self, room_id: str, username: str) -> Connection | None:
        return next(
            (c for c in self.rooms.get(room_id, []) if c.username == username),
            None,
        )


    # --- Broadcast ---

    async def broadcast(self, room_id: str, message: WireMessage, exclude: str | None = None) -> None:
        connections = self.rooms.get(room_id, [])
        sender = message.sender_id if isinstance(message, ChatMessage) else "system"
        logger.info(
            "broadcast room=%s type=%s sender=%s  ws=%d sse=%d bot=%d",
            room_id, message.type, sender,
            sum(1 for c in connections if c.__class__.__name__ == "WebSocketConnection"),
            sum(1 for c in connections if c.__class__.__name__ == "SseConnection"),
            sum(1 for c in connections if c.__class__.__name__ == "BotConnection"),
        )

        dead: list[Connection] = []
        for conn in list(connections):
            if conn.username == exclude:
                continue
            try:
                await conn.send(message)
            except Exception:
                dead.append(conn)
                logger.exception(
                    "Error sending broadcast message to user %s in room %s. Removing connection. Message: %s",
                    conn.username, room_id, message)
        for conn in dead:
            self.rooms.get(room_id, []).remove(conn)

    async def shutdown(self) -> None:
        """Close all connections in all rooms, e.g. on server shutdown."""
        for connections in self.rooms.values():
            for conn in connections:
                await conn.close()
        self.rooms.clear()



# ---------- Message Handler ----------

class MessageHandler:

    def __init__(self,
                 inbound: asyncio.Queue,
                 outbound: asyncio.Queue,
                 chat_manager: ChatManager,
                 conns: ConnectionManager,
                 shutdown_event: asyncio.Event) -> None:

        self.inbound: asyncio.Queue = inbound
        self.outbound: asyncio.Queue = outbound
        self.shutdown_event = shutdown_event # asyncio.Event()
        self.conns = conns
        self.chat_mgr = chat_manager

        self._tasks: list[asyncio.Task] = []
        # active rooms are tracked to manage bot connections and avoid repeating the same logic for every message
        self._active_rooms: set[str] = set()  # track active rooms to manage bot connections

    async def start(self) -> None:
        """Start the connection manager's main loop to process inbound messages."""
        _in_task = asyncio.create_task(self._process_inbound_messages())
        _out_task = asyncio.create_task(self._process_outbound_messages())

        def handle_exception(task):
            if not task.cancelled():
                exc = task.exception()
                if exc:
                    logger.error("msg_handler failed", exc_info=exc)
        _in_task.add_done_callback(handle_exception)
        _out_task.add_done_callback(handle_exception)

        self._tasks = [_in_task, _out_task]

    async def shutdown(self) -> None:
        """Signal the message handler to stop processing messages and clean up resources."""
        for task in self._tasks:
            task.cancel()

    # --- Bot helpers ---

    def get_or_create_bot_conn(self, room_id: str, bot_name: str) -> BotConnection:
        existing = self.conns.get(room_id, bot_name)
        if isinstance(existing, BotConnection):
            logger.info("Found existing bot connection for bot=%s in room=%s", bot_name, room_id)
            return existing
        logger.info("Creating new bot connection for bot=%s in room=%s", bot_name, room_id)
        bot = BotConnection(bot_name, room_id, outbox=self.outbound)
        bot.start()
        self.conns.add(room_id, bot)
        return bot

    # --- Queue Processing ---

    async def _process_inbound_messages(self):
        """Continuously process messages from the inbound queue."""
        logger.info("Messagehandler listening for inbound messages ...")
        while True:
            if self.shutdown_event.is_set():
                logger.info("MH: Shutdown event set, stopping inbound message processing loop ...")
                break

            message = await self.inbound.get()
            logger.info("MH: Messagehandler got message %s", message)
            try:
                await self._process_message(message)
            finally:
                self.inbound.task_done()

    async def _process_message(self, message: ChatMessage) -> None:
        """Process a single inbound ChatMessage from the queue."""
        logger.info("MH: Processing message: %s", message)
        room_id = message.room_id
        sender = message.sender_id
        content = message.content

        # route the message to the appropriate room
        if room_id not in self._active_rooms:
            room = self.chat_mgr.get_room(room_id)
            if not room:
                logger.error("MH: Received message for non-existent room %s: %s", room_id, message)
                # for testing purpuses we always create a DM room between the sender and a bot, and route all messages there
                # todo implement proper room management and routing logic, e.g. by including a room_id in the message metadata and validating it here, instead of auto-creating DM rooms for any unknown room IDs
                return

            # get all room members and check if any are bots,
            # if so make sure a bot connection exists for them
            members = self.chat_mgr.get_members(room_id)
            for member in members:
                if member.member_type == "bot":
                    self.get_or_create_bot_conn(room_id, member.username)
                    # notify the room that the bot has joined
                    await self.conns.broadcast(room_id, SystemMessage(room_id=room_id,
                                                                      content=f"Bot {member.username} has joined the room."))

            # add active room to the set to avoid repeating this logic for every message
            self._active_rooms.add(room_id)

        # store inbound messages chat history
        if isinstance(message, ChatMessage):
            self.chat_mgr.add_message(room_id, sender, message.content)

        # inspect the first content part to check for commands (e.g. to trigger bot actions or other system events)
        if content and len(content) > 0 and content[0].type == "text":
            text = content[0].text.strip()
            print(f"MH: Inspecting message content for commands: '{text}'")
            if text.startswith("$"):
                command = text[1:].split()[0]  # get the command word after the "/"
                logger.info("MH: Detected command '%s' in message: %s", command, message)
                # handle_user_command(command)
                await self.conns.broadcast(room_id, SystemMessage(room_id=room_id,
                                                                  content=f"User {sender} issued command: {command}"))
                return

        # broadcast the original message to all members in the room (including bots)
        await self.conns.broadcast(room_id, message)

    async def _process_outbound_messages(self):
        """Continuously process messages from the outbound queue and broadcast to rooms."""
        logger.info("Messagehandler listening for outbound messages ...")
        while True:
            if self.shutdown_event.is_set():
                logger.info("MH: Shutdown event set, stopping outbound message processing loop ...")
                break

            message: ChatMessage | SystemMessage = await self.outbound.get()
            logger.info("Messagehandler got outbound message %s", message)
            try:
                # store outbound messages in chat history
                if isinstance(message, ChatMessage):
                    self.chat_mgr.add_message(message.room_id, message.sender_id, message.content)

                await self.conns.broadcast(message.room_id, message)
            finally:
                self.outbound.task_done()
