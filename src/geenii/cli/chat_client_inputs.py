import asyncio
import contextlib
import json
import os
from typing import AsyncIterator, Optional


class InputReader:
    """Async iterator of strings representing outbound chat messages. Subclass and implement __aiter__()."""

    async def __aiter__(self) -> AsyncIterator[str]:
        raise NotImplementedError


class StdinInput(InputReader):
    """Reads lines from stdin in a thread (won't be instantly cancellable until Enter)."""

    def __init__(self, prompt: str) -> None:
        self.prompt = prompt

    async def __aiter__(self) -> AsyncIterator[str]:
        loop = asyncio.get_running_loop()
        while True:
            try:
                line = await loop.run_in_executor(None, lambda: input(self.prompt))
            except (EOFError, KeyboardInterrupt):
                return
            yield line


class SocketInput(InputReader):
    """Reads newline-delimited lines from a TCP socket."""

    def __init__(self, host: str, port: int, *, encoding: str = "utf-8") -> None:
        self.host = host
        self.port = port
        self.encoding = encoding

    async def __aiter__(self) -> AsyncIterator[str]:
        reader, writer = await asyncio.open_connection(self.host, self.port)
        try:
            while True:
                b = await reader.readline()
                if not b:
                    return
                yield b.decode(self.encoding, errors="replace")
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()


class PollHttpInput(InputReader):
    """
    Polls an HTTP endpoint that returns either:
      - a JSON object: {"messages": ["hi", "there"]} or {"message": "hi"}
      - plain text (one message)
    Uses stdlib urllib to avoid extra deps.

    NOTE: polling in a tight loop is rude; keep interval >= 0.5s.
    """

    def __init__(
        self,
        url: str,
        *,
        interval_s: float = 1.0,
        timeout_s: float = 5.0,
    ) -> None:
        self.url = url
        self.interval_s = interval_s
        self.timeout_s = timeout_s

    async def __aiter__(self) -> AsyncIterator[str]:
        import urllib.request
        import urllib.error

        loop = asyncio.get_running_loop()

        def _fetch() -> Optional[str]:
            req = urllib.request.Request(self.url, headers={"Accept": "application/json, text/plain;q=0.9"})
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                return resp.read().decode("utf-8", errors="replace")

        while True:
            try:
                body = await loop.run_in_executor(None, _fetch)
            except Exception:
                # Swallow transient errors; caller can log if desired
                await asyncio.sleep(self.interval_s)
                continue

            if body:
                body = body.strip()
                if body:
                    # Try JSON first
                    try:
                        obj = json.loads(body)
                        if isinstance(obj, dict):
                            if "messages" in obj and isinstance(obj["messages"], list):
                                for m in obj["messages"]:
                                    if isinstance(m, str):
                                        yield m
                            elif "message" in obj and isinstance(obj["message"], str):
                                yield obj["message"]
                        elif isinstance(obj, list):
                            for m in obj:
                                if isinstance(m, str):
                                    yield m
                    except json.JSONDecodeError:
                        # Fallback: treat as plain text message
                        yield body

            await asyncio.sleep(self.interval_s)




class UnixSocketInput(InputReader):
    """
    Reads newline-delimited messages from a Unix domain socket.

    Expected usage:
        echo "hello" | socat - UNIX-CONNECT:/tmp/chat.sock

    or another local process writing lines.

    Each newline-delimited line becomes one outbound chat message.
    """

    def __init__(
        self,
        path: str,
        *,
        encoding: str = "utf-8",
        reconnect: bool = True,
        reconnect_delay: float = 1.0,
    ) -> None:
        self.path = path
        self.encoding = encoding
        self.reconnect = reconnect
        self.reconnect_delay = reconnect_delay

    async def __aiter__(self) -> AsyncIterator[str]:
        while True:
            try:
                reader, writer = await asyncio.open_unix_connection(self.path)
                print(f"UnixSocketInput: connected to {self.path}")
            except FileNotFoundError as e:
                print(f"UnixSocketInput: no socket at {self.path} ({e})")
            except ConnectionRefusedError as e:
                print(f"UnixSocketInput: nothing listening at {self.path} ({e})")
            except OSError as e:
                # This will reveal the real errno on macOS (very important)
                print(f"UnixSocketInput: open_unix_connection failed for {self.path}: {e!r}")
            except Exception as e:
                print(f"UnixSocketInput: unexpected error for {self.path}: {e!r}")
                if not self.reconnect:
                    return
                await asyncio.sleep(self.reconnect_delay)
                continue

            try:
                while True:
                    line = await reader.readline()
                    if not line:
                        break
                    yield line.decode(self.encoding, errors="replace")
            except asyncio.CancelledError:
                raise
            except Exception:
                # socket died unexpectedly
                print(f"UnixSocketInput: connection lost, will {'reconnect' if self.reconnect else 'stop'}")
                pass
            finally:
                writer.close()
                with contextlib.suppress(Exception):
                    await writer.wait_closed()

            if not self.reconnect:
                return

            await asyncio.sleep(self.reconnect_delay)



class UnixSocketServerInput(InputReader):
    """
    Unix domain socket *server* input source.

    - Binds & listens on a filesystem socket path.
    - Accepts one or many clients.
    - Reads newline-delimited messages from clients.
    - Emits each line as an outbound chat message.

    Typical usage (in another terminal):
        socat - UNIX-CONNECT:/tmp/chat_in.sock
        (then type lines + Enter)

    Notes:
    - Removes stale socket file on startup.
    - On shutdown, closes server and unlinks socket file.
    """

    def __init__(
        self,
        path: str,
        *,
        encoding: str = "utf-8",
        max_line_bytes: int = 64 * 1024,
        backlog: int = 100,
        unlink_on_close: bool = True,
    ) -> None:
        self.path = path
        self.encoding = encoding
        self.max_line_bytes = max_line_bytes
        self.backlog = backlog
        self.unlink_on_close = unlink_on_close

        self._queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        self._server: Optional[asyncio.AbstractServer] = None
        self._serve_task: Optional[asyncio.Task[None]] = None
        self._closing = False

    async def _ensure_server(self) -> None:
        if self._server is not None:
            return

        # Remove stale socket file before binding.
        try:
            os.unlink(self.path)
        except FileNotFoundError:
            pass

        # check if directory exists
        dir_path = os.path.dirname(self.path)
        if dir_path and not os.path.exists(dir_path):
            print(f"UnixSocketServer: Warning: Base directory {dir_path} does not exist")

        #print(f"UnixSocketServerInput: starting server on {self.path} ...")
        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=self.path,
            backlog=self.backlog,
        )
        # Run the server in the background while __aiter__ drains the queue.
        self._serve_task = asyncio.create_task(self._server.serve_forever())

        # Wait a moment to detect immediate bind errors (e.g. permission issues, invalid path).
        #await asyncio.sleep(0.1)
        #if self._server is None:
        #    print(f"UnixSocketServerInput: failed to start server on {self.path}")
        #    raise RuntimeError("Failed to start Unix socket server")
        #print(f"UnixSocketServerInput: server started on {self.path}")

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while True:
                b = await reader.readline()
                if not b:
                    return
                if len(b) > self.max_line_bytes:
                    # Drop overlong lines to avoid memory abuse.
                    continue
                line = b.decode(self.encoding, errors="replace").rstrip("\r\n")
                if line:
                    await self._queue.put(line)
        except asyncio.CancelledError:
            raise
        except Exception:
            # Client misbehaved or disconnected abruptly.
            return
        finally:
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

    async def aclose(self) -> None:
        """Stop listening, close all connections, and optionally unlink the socket file."""
        if self._closing:
            return
        self._closing = True

        if self._serve_task is not None:
            self._serve_task.cancel()
            with contextlib.suppress(Exception):
                await self._serve_task
            self._serve_task = None

        if self._server is not None:
            self._server.close()
            with contextlib.suppress(Exception):
                await self._server.wait_closed()
            self._server = None

        if self.unlink_on_close:
            with contextlib.suppress(FileNotFoundError):
                os.unlink(self.path)

        # Unblock iterator if it's waiting.
        await self._queue.put(None)

    async def __aiter__(self) -> AsyncIterator[str]:
        await self._ensure_server()
        try:
            while True:
                item = await self._queue.get()
                if item is None:
                    return
                yield item
        finally:
            # If the consumer stops iterating, clean up the server.
            print("UnixSocketServerInput: shutting down server")
            await self.aclose()
