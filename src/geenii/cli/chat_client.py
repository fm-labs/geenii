#!/usr/bin/env python3
"""
CLI client for the geenii-chat server.

Set CHAT_USERNAME env var or pass --username globally:

    export CHAT_USERNAME=alice
    export CHAT_SERVER=http://localhost:3333

Usage:
    python chat_client.py --username alice create-room --name "general"
    python chat_client.py --username alice list-rooms
    python chat_client.py --username alice join    --room ROOM_ID
    python chat_client.py --username alice invite  --room ROOM_ID --target bob
    python chat_client.py --username alice send    --room ROOM_ID --text "Hello!"
    python chat_client.py --username alice poll    --room ROOM_ID [--last 10] [--after 5]
    python chat_client.py --username alice chat    --room ROOM_ID
"""

import asyncio
import hashlib
import json
import sys
from datetime import datetime
from typing import Any, AsyncIterator

import click
import httpx
import websockets

from geenii.cli.base import BaseCli
from geenii.cli.chat_client_inputs import StdinInput, InputReader
from geenii.chat.chat_manager import dm_room_id

DEFAULT_BASE_URL = "http://localhost:31313"
API_PREFIX = "/chat"


# ---------- Helpers ----------

def api_url(base: str, path: str) -> str:
    return f"{base}{API_PREFIX}{path}"


def ws_url(base: str, path: str) -> str:
    return base.replace("http://", "ws://").replace("https://", "wss://") + API_PREFIX + path


def make_token(username: str) -> str:
    """Create a dummy bearer token from the username (SHA-256 hash)."""
    return hashlib.sha256(username.encode()).hexdigest()


def auth_headers(username: str) -> dict[str, str]:
    """Return Authorization header with a dummy bearer token."""
    return {"Authorization": f"Bearer {make_token(username)}"}


def handle_response(resp: httpx.Response) -> dict | list:
    if resp.status_code >= 400:
        try:
            detail = resp.json().get("detail", resp.text)
        except Exception:
            detail = resp.text
        click.secho(f"Error {resp.status_code}: {detail}", fg="red", err=True)
        sys.exit(1)
    return resp.json()


def extract_text(content: list[dict]) -> str:
    """Extract displayable text from a message content array."""
    parts = []
    for part in content:
        match part.get("type"):
            case "text":
                parts.append(part["text"])
            case "image":
                parts.append(f'[image: {part.get("alt") or part["url"]}]')
            case "audio":
                parts.append(f'[audio: {part["url"]}]')
            case "function":
                parts.append(f'[fn:{part["name"]}]')
            case _:
                parts.append(str(part))
    return " ".join(parts)


def format_timestamp(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%H:%M:%S")
    except Exception:
        return ts


# ---------- CLI ----------

class ChatClientCli(BaseCli):

    def __init__(self, cli: click.core.Group):
        super().__init__(cli)

        @cli.group()
        @click.option("--server", default=DEFAULT_BASE_URL, envvar="CHAT_SERVER",
                      show_default=True, help="Base URL of the chat server.")
        @click.option("--username", required=True, envvar="CHAT_USERNAME",
                      help="Your username (or set CHAT_USERNAME).")
        @click.pass_context
        def chat(ctx: click.Context, server: str, username: str) -> None:
            """CLI client for the geenii-chat server (Experimental!)."""
            ctx.ensure_object(dict)
            ctx.obj["server"] = server
            ctx.obj["username"] = username
            ctx.obj["headers"] = auth_headers(username)


        # --- create-room ---

        @chat.command("create-room")
        @click.option("--name", required=True, help="Room name.")
        @click.option("--private", "is_private", is_flag=True, help="Make the room private.")
        @click.option("--password", default=None, help="Set a room password.")
        @click.pass_context
        def create_room_cmd(ctx: click.Context, name: str, is_private: bool, password: str | None) -> None:
            """Create a new chat room."""
            server, headers = ctx.obj["server"], ctx.obj["headers"]
            body: dict = {"name": name}
            if is_private:
                body["is_public"] = False
            if password:
                body["password"] = password

            with httpx.Client(headers=headers) as client:
                resp = client.post(api_url(server, ""), json=body)
            room = handle_response(resp)
            click.echo(f"Room created: {room['name']}  (id: {room['id']}, owner: {room['owner']})")


        # --- list-rooms ---

        @chat.command("list-rooms")
        @click.pass_context
        def list_rooms_cmd(ctx: click.Context) -> None:
            """List all available rooms."""
            server, headers = ctx.obj["server"], ctx.obj["headers"]
            with httpx.Client(headers=headers) as client:
                resp = client.get(api_url(server, ""))
            rooms = handle_response(resp)
            if not rooms:
                click.echo("No rooms found.")
                return
            for r in rooms:
                visibility = "private" if not r["is_public"] else "public"
                click.echo(f"  {r['name']:20s}  {visibility:7s}  owner={r['owner']:15s}  id={r['id']}")


        # --- join ---
        # @chat.command()
        # @click.option("--room", required=True, help="Room ID.")
        # @click.option("--password", default=None, help="Room password (if required).")
        # @click.option("--bot", is_flag=True, help="Join as a bot member.")
        # @click.pass_context
        # def join(ctx: click.Context, room: str, password: str | None, bot: bool) -> None:
        #     """Join a room."""
        #     server, headers, username = ctx.obj["server"], ctx.obj["headers"], ctx.obj["username"]
        #     body: dict = {"username": username}
        #     if password:
        #         body["password"] = password
        #     if bot:
        #         body["member_type"] = "bot"
        #
        #     with httpx.Client(headers=headers) as client:
        #         resp = client.post(api_url(server, f"/rooms/{room}/join"), json=body)
        #     member = handle_response(resp)
        #     click.echo(f"Joined room {room} as {member['username']} (status: {member['status']})")
        #
        #
        # # --- invite ---
        #
        # @chat.command()
        # @click.option("--room", required=True, help="Room ID.")
        # @click.option("--target", required=True, help="Username to invite.")
        # @click.option("--bot", is_flag=True, help="Invite as a bot member.")
        # @click.pass_context
        # def invite(ctx: click.Context, room: str, target: str, bot: bool) -> None:
        #     """Invite a user to a room (owner only)."""
        #     server, headers = ctx.obj["server"], ctx.obj["headers"]
        #     body: dict = {"username": target}
        #     if bot:
        #         body["member_type"] = "bot"
        #
        #     with httpx.Client(headers=headers) as client:
        #         resp = client.post(api_url(server, f"/rooms/{room}/invite"), json=body)
        #     member = handle_response(resp)
        #     click.echo(f"Invited {member['username']} to room {room}")


        # --- send ---

        @chat.command()
        @click.option("--room", required=True, help="Room ID.")
        @click.option("--text", required=True, help="Message text.")
        @click.pass_context
        def send(ctx: click.Context, room: str, text: str) -> None:
            """Send a text message to a room via REST."""
            server, headers = ctx.obj["server"], ctx.obj["headers"]
            body = {"content": [{"type": "text", "text": text}]}

            with httpx.Client(headers=headers) as client:
                resp = client.post(api_url(server, f"/rooms/{room}/messages"), json=body)
            msg = handle_response(resp)
            click.echo(f"[{format_timestamp(msg['created_at'])}] {msg['username']}: {extract_text(msg['content'])}")


        # --- poll ---

        @chat.command()
        @click.option("--room", required=True, help="Room ID.")
        @click.option("--last", "last_n", type=int, default=None, help="Show only the last N messages.")
        @click.option("--after", type=int, default=None, help="Show messages after this message ID.")
        @click.pass_context
        def poll(ctx: click.Context, room: str, last_n: int | None, after: int | None) -> None:
            """Poll messages from a room."""
            server, headers = ctx.obj["server"], ctx.obj["headers"]
            params: dict = {}
            if after is not None:
                params["after"] = after

            with httpx.Client(headers=headers) as client:
                resp = client.get(api_url(server, f"/rooms/{room}/messages"), params=params)
            messages = handle_response(resp)

            if last_n:
                messages = messages[-last_n:]

            if not messages:
                click.echo("No messages.")
                return

            for msg in messages:
                ts = format_timestamp(msg["created_at"])
                text = extract_text(msg["content"])
                click.echo(f"  [{ts}] #{msg['id']} {msg['username']}: {text}")



        @chat.command()
        @click.option("--room", required=True, help="Room ID.")
        @click.pass_context
        def start(ctx: click.Context, room: str) -> None:
            """Start an interactive WebSocket chat session."""
            server, headers, username = ctx.obj["server"], ctx.obj["headers"], ctx.obj["username"]

            # DM session
            if room.startswith("@"):
                peer_username = room[1:]
                room = dm_room_id(peer_username, username)
                click.echo(f"Connecting to DM room with {peer_username} (room id: {room}) ...")

            session = LiveChatSession(server, room, username, headers, inputs=[
                StdinInput(f"{username}> "),
                #UnixSocketServerInput(f"{os.getcwd()}/tmp/chat-{room}.sock"),
            ], )

            try:
                asyncio.run(session.run())
            except (KeyboardInterrupt, SystemExit):
                print("\nSession interrupted...")

                # Fallback if signal handler didn't fire (e.g. Windows)
                if session.transport is not None:
                    asyncio.run(session.close())

                sys.exit(0)
# --- chat ---


# -----------------------------
# Message handling
# -----------------------------

class ChatMessageHandler:
    """Handles incoming messages by type. Subclass to customise behaviour."""

    def __init__(self, username: str) -> None:
        self.username = username

    def handle_server_message(self, raw: str) -> None:
        """Dispatch an incoming message to the appropriate handler by type."""

        print("Received raw message:", raw)
        try:
            data = json.loads(raw)
            msg_type = data.get("type", "")
        except json.JSONDecodeError:
            data = {"raw": raw}
            msg_type = "unknown"

        handler = getattr(self, f"on_{msg_type}", self.on_unknown)
        handler(data)

    def handle_input(self, text: str) -> None:
        """Handle user input from stdin (or other sources). Override to customise."""
        print("Received user input:", text)
        pass


class CliChatMessageHandler(ChatMessageHandler):
    """
    Handles incoming WebSocket messages by type.
    Default implementation prints system messages and chat messages to the console.
    """

    def __init__(self, username: str) -> None:
        super().__init__(username)

    def on_system(self, data: dict) -> None:
        click.echo(f"\r  *** {data['content']} ***")

    def on_message(self, data: dict) -> None:
        ts = format_timestamp(data.get("created_at", ""))
        text = extract_text(data.get("content", []))
        who = data.get("sender_id", "?")
        click.echo(f"\r  [{ts}] {who}: {text}")

    def on_unknown(self, data: dict) -> None:
        click.echo(f"\r  {data}")



# -----------------------------
# Chat session
# -----------------------------

class ChatSessionTransport:
    """Abstract transport for sending and receiving chat messages."""

    async def connect(self) -> None:
        raise NotImplementedError

    async def send(self, payload: str) -> None:
        raise NotImplementedError

    async def read(self) -> AsyncIterator[str]:
        yield "Not implemented"

    async def close(self) -> None:
        """Close the transport cleanly."""
        pass

    #async def __aiter__(self) -> AsyncIterator[str]:
    #    return self.read()


class WebSocketChatSessionTransport(ChatSessionTransport):
    """WebSocket transport implementation for chat sessions."""

    def __init__(self, uri: str, headers: dict[str, str]) -> None:
        self.uri = uri
        self.headers = headers
        self.ws: websockets.ClientConnection | None = None

    async def connect(self) -> None:
        """Establish the WebSocket connection."""
        click.echo(f"Connecting to {self.uri} ...")
        self.ws = await websockets.connect(self.uri, additional_headers=self.headers)
        click.echo("Connected.")

    async def send(self, payload: str) -> None:
        """Send a message over the WebSocket."""
        assert self.ws is not None
        try:
            await self.ws.send(payload, text=True)
        except websockets.ConnectionClosed:
            click.echo("\nConnection closed, cannot send message.")

    async def read(self) -> AsyncIterator[str]:
        """Async generator that yields incoming messages from the WebSocket."""
        assert self.ws is not None
        try:
            async for raw in self.ws:
                yield raw
        except websockets.ConnectionClosed:
            click.echo("\nConnection closed by server.")
        except asyncio.CancelledError:
            pass

    async def close(self) -> None:
        """Close the WebSocket connection cleanly."""
        if self.ws is not None:
            try:
                await self.ws.close()
            except Exception:
                pass
            self.ws = None

class LiveChatSession:
    """Tracks an active WebSocket chat session for clean shutdown."""

    def __init__(
        self,
        server: str,
        room_id: str,
        username: str,
        headers: dict[str, str],
        transport: ChatSessionTransport | None = None,
        handler: ChatMessageHandler | None = None,
        inputs: list[InputReader] | None = None,
    ) -> None:
        self.server = server
        self.room_id = room_id
        self.username = username
        self.headers = {**headers}

        self.handler = handler or CliChatMessageHandler(username)
        self.inputs = inputs or [StdinInput(prompt=f"{self.username}> ")]

        #self.ws: websockets.ClientConnection | None = None
        self.transport: ChatSessionTransport = transport or WebSocketChatSessionTransport(
            ws_url(server, f"/ws?username={username}&room_id={room_id}&token={make_token(username)}"),
            headers,
        )
        self._tasks: list[asyncio.Task[Any]] = []

        self._shutdown: asyncio.Event = asyncio.Event()
        self._closing: asyncio.Lock = asyncio.Lock()

    async def connect(self) -> None:
        #uri = ws_url(self.server, f"/rooms/{self.room_id}/ws?username={self.username}")
        #click.echo(f"Connecting to {uri} ...")
        #self.ws = await websockets.connect(uri, additional_headers=self.headers)
        await self.transport.connect()
        click.echo(f"Connected as {self.username}. Ctrl+C to quit.\n")

    async def close(self) -> None:
        """Cancel tasks and close the WebSocket cleanly (idempotent)."""
        async with self._closing:
            if self._shutdown.is_set() and self.transport is None:
                return

            click.echo(f"Shutting down chat session... ({len(self._tasks)} tasks)")
            self._shutdown.set()

            # Cancel background tasks
            for t in self._tasks:
                if not t.done():
                    t.cancel()

            # Don't hang forever (stdin input thread can block)
            if self._tasks:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*self._tasks, return_exceptions=True),
                        timeout=1.0,
                    )
                except asyncio.TimeoutError:
                    pass

            if self.transport is not None:
                try:
                    await self.transport.close()
                except Exception:
                    pass
                self.transport = None

            click.echo("Session closed.")

    async def _receiver(self) -> None:
        """
        Background task to receive messages from the WebSocket and dispatch to the handler.
        :return:
        """
        assert self.transport is not None
        try:
            async for raw in self.transport.read():
                if self._shutdown.is_set():
                    break

                self.handler.handle_server_message(raw)

                # re-print prompt if stdin is one of the sources
                if any(isinstance(src, StdinInput) for src in self.inputs):
                    click.echo(f"{self.username}> ", nl=False)
        except asyncio.CancelledError:
            pass
        except Exception:
            if not self._shutdown.is_set():
                click.echo("\nError receiving message from server.", err=True)

    async def _send_text(self, text: str) -> None:
        """Helper to send a text message over the transport to the server."""
        assert self.transport is not None
        payload = {"content": [{"type": "text", "text": text}]}
        await self.transport.send(json.dumps(payload))

    async def _send_image(self, image: str):
        """Helper to send an image message over the transport to the server."""
        assert self.transport is not None
        payload = {"content": [{"type": "image", "url": image}]}
        await self.transport.send(json.dumps(payload))

    async def _send_audio(self, audio: str):
        """Helper to send an audio message over the transport to the server."""
        assert self.transport is not None
        payload = {"content": [{"type": "audio", "url": audio}]}
        await self.transport.send(json.dumps(payload))

    async def _send_tool_call(self, name: str, args: dict):
        """Helper to send a tool call message over the transport to the server."""
        assert self.transport is not None
        payload = {"content": [{"type": "function", "name": name, "args": args}]}
        await self.transport.send(json.dumps(payload))


    async def _input_reader(self, src: InputReader) -> None:
        """
        Read outbound lines from a single input source and send them to the server as messages.
        This runs in a background task for each input source.
        """
        print(f"Started input pump for {type(src).__name__}")
        assert self.transport is not None
        try:
            # Note: if the input source is blocking (e.g. stdin), this task may not respond to cancellation until input is received.
            async for line in src:
                if self._shutdown.is_set():
                    return

                text = (line or "").strip()
                if not text:
                    continue

                # hardcoded exit handler for now - if user types "/exit", we close the session
                if text.lower() in ("/exit", "/quit"):
                    click.echo("Exit command received, closing session...")
                    await self.close()
                    return

                # handle the input message
                # for now we just send the text as a simple message content array with one text part
                # todo - add support for structured messages with images, functions, etc. (not just text)
                # todo - add support for commands (e.g. "/leave", "/invite bob", etc.)
                try:
                    await self._send_text(text)
                except Exception as e:
                    if not self._shutdown.is_set():
                        click.echo(f"\nTransport error, cannot send message. Error: {repr(e)}", err=True)
                    return
        except asyncio.CancelledError:
            pass

    async def run(self) -> None:
        assert self.transport is not None
        await self.connect()

        receiver_task = asyncio.create_task(self._receiver(), name="receiver")
        input_tasks = [asyncio.create_task(self._input_reader(src), name=f"input:{type(src).__name__}")
                       for src in self.inputs]

        self._tasks = [receiver_task, *input_tasks]

        try:
            # Exit when *any* task finishes (server close, stdin EOF, socket close, etc.)
            await asyncio.wait(self._tasks, return_when=asyncio.FIRST_COMPLETED)
        finally:
            await self.close()
            print("Chat session ended.")



if __name__ == "__main__":
    cli = click.CommandCollection()
    ChatClientCli(cli)
    cli()
