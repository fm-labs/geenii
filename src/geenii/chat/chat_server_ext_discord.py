import asyncio
import logging

import discord

from geenii.chat.chat_manager import ChatManager
from geenii.chat.chat_models import WireMessage, ChatMessage, SystemMessage, ContentPart, TextContent, ImageContent, \
    FileContent, EmbedContent
from geenii.chat.chat_server_core import ConnectionManager, Connection

logger = logging.getLogger(__name__)


class DiscordConnection(Connection):
    def __init__(self, username: str, channel: discord.DMChannel | discord.GroupChannel) -> None:
        self._username = username # discord:[user_id]
        self._channel = channel

    @property
    def username(self) -> str:
        return self._username

    async def send(self, message: WireMessage) -> None:
        """Send message to the Discord channel."""
        if not self._channel:
            logger.warning("DiscordConnection for user %s has no channel to send messages to.", self._username)
            return

        logger.info("DiscordConnection sending message for user %s: %s", self._username, message)

        if isinstance(message, ChatMessage):
            if message.sender_id == self._username:
                logger.debug("Skipping echo of own message for user %s.", self._username)
                return
            text = " ".join(
                part.text for part in message.content
                if isinstance(part, TextContent)
            )
        elif isinstance(message, SystemMessage):
            text = f"**[System]**: {message.content}"
        else:
            text = f"[Unsupported message type: {message.type}]"

        if text:
            try:
                await self._channel.send(text)
            except Exception:
                logger.exception("Error sending message to Discord channel for user %s", self._username)


    async def close(self) -> None:
        """Close the Discord connection."""
        # Note: We do not actually close the Discord channel here,
        # as it may be shared and we don't want to disrupt other participants.
        # Instead, we just stop sending messages to it.
        logger.info("DiscordConnection for user %s is closing", self._username)
        try:
            # this will trigger on every server shutdown,
            # so we should avoid sending too many messages to Discord channels in a short time
            # await self._channel.send("Connection is closing. Goodbye!")
            pass
        except Exception as e:
            logger.exception("Error sending closing message to Discord channel for user %s: %s", self._username, e)



# ----- Connector -----


class DiscordBotConnector:
    """
    A connector that runs a Discord bot client to receive DMs and forward them into the chat system.

    Routes DMs to the appropriate chat room based on the sender's Discord user ID.

    Each DM channel is mapped to a unique chat room, and the connection manager maintains a
    DiscordConnection for each active DM channel to send messages back to the user.
    """

    def __init__(self, token: str, conns: ConnectionManager, chat_manager: ChatManager, queue: asyncio.Queue, shutdown_event: asyncio.Event):
        self._conns = conns
        self._chat_mgr = chat_manager
        self._queue = queue  # shared queue to enqueue incoming messages for processing by the main message handler loop
        self._shutdown_event = shutdown_event

        intents = discord.Intents.default()
        intents.message_content = True  # needed if you want message content in some contexts
        intents.dm_messages = True  # receive DMs
        intents.guilds = True
        intents.members = True  # needed to fetch users reliably in some cases

        self.token = token
        self.client = discord.Client(intents=intents)
        self.client.event(self.on_ready)
        self.client.event(self.on_message)

        self._task: asyncio.Task | None = None

    async def on_ready(self):
        """Called when the bot has successfully connected to Discord and is ready to receive events."""
        print(f"Logged in as {self.client.user} (id={self.client.user.id})")

    async def on_message(self, message: discord.Message):
        """Called when a new message arrives (DM or guild). Routes to the appropriate chat room and enqueues them for processing."""
        if message.author.id == self.client.user.id:
            return

        if isinstance(message.channel, discord.DMChannel):
            print(f"DM from {message.author} ({message.author.id}): {message.content}")
            print("ChannelID:", message.channel.id)
            await message.channel.send("[ext] Got your message 👍")

            # todo mapping of discord user ID to chat server username. discord:{user_id} -> {username}
            # todo mapping of user bots. username -> bot_id

            username = f"discord:{message.author.id}"
            bot_id = f"geenii_bot:default"

            # ensure DM room exists in chat manager, if not create it
            dm_room = self._chat_mgr.get_dm_room(owner=username, peer=bot_id, auto_create=True)
            room_id = dm_room.id

            # ensure connection exists for this DM channel and user
            self.get_or_create_dm_connection(room_id, username, message.channel)

            content = self.map_discord_message_content(message)

            # enqueue the message for processing by the main message handler loop
            await self._queue.put(ChatMessage(
                room_id=room_id,
                sender_id=username,
                content=content,
            ))

            # direct broadcast to other connections in same room (if any)
            # await self._conns.broadcast(room_id,{
            #     "type": "message",
            #     "username": username,
            #     "content": content,
            # }, exclude=username)
        else:
            print(f"Message in guild {message.guild.name} from {message.author}: {message.content}")
            await message.channel.send("Got your message in the guild 👍")

    @staticmethod
    def map_discord_message_content(message: discord.Message) -> list[ContentPart]:
        """Map a Discord message to a list of typed ContentPart models."""
        content_parts: list[ContentPart] = []

        if message.content:
            content_parts.append(TextContent(text=message.content))

        for attachment in message.attachments:
            logger.info("Processing attachment: filename=%s, content_type=%s, size=%d bytes",
                        attachment.filename, attachment.content_type, attachment.size)
            if attachment.content_type and attachment.content_type.startswith("image/"):
                content_parts.append(ImageContent(
                    url=attachment.url,
                    alt=attachment.filename,
                ))
            else:
                content_parts.append(FileContent(
                    url=attachment.url,
                    filename=attachment.filename,
                    content_type=attachment.content_type,
                    size=attachment.size,
                ))

        for embed in message.embeds:
            logger.info("Processing embed: title=%s", embed.title)
            content_parts.append(EmbedContent(
                title=embed.title,
                description=embed.description,
                url=embed.url,
                thumbnail_url=embed.thumbnail.url if embed.thumbnail else None,
                video_url=embed.video.url if embed.video else None,
            ))

        return content_parts


    def get_or_create_dm_connection(self,
                                    room_id: str,
                                    username: str,
                                    channel: discord.DMChannel | discord.GroupChannel) -> DiscordConnection:
        """
        Ensures there is a DiscordConnection for the given DM channel and user, creating one if necessary.
        Raises an error if there is a conflicting non-Discord connection.
        """
        conn = self._conns.get(room_id, username)
        if isinstance(conn, DiscordConnection):
            logger.info("Found existing Discord connection for user=%s in channel=%s", username, channel.id)
            return conn

        if conn is not None:
            # logger.warning("Existing non-Discord connection found for user=%s in channel=%s. Replacing with DiscordConnection.", username, channel.id)
            # self._conns.remove(room_id, conn)
            logger.error(
                "Found existing connection for user=%s in channel=%s, but is not a discord connection. This is fatal.",
                username, channel.id)
            raise RuntimeError(f"Connection conflict for user={username} in channel={channel.id}")

        conn = DiscordConnection(username, channel)
        self._conns.add(room_id, conn)
        logger.info("Created new Discord connection for user=%s in channel=%s", username, channel.id)
        return conn

    async def start(self):
        self._task = asyncio.create_task(self.client.start(self.token))

    async def stop(self):
        if self._task:
            self._task.cancel()
        await self.client.close()

