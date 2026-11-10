import asyncio
import base64
import logging
import os

from fastmcp import Client
from fastmcp.client.logging import LogMessage
from fastmcp.mcp_config import MCPConfig
from mcp_types import (
    BlobResourceContents,
    CallToolResult,
    Prompt,
    Resource,
    TextResourceContents,
    Tool,
)

from geenii.config import MCP_INIT_TIMEOUT
from geenii.utils.async_bridge import run_sync

logger = logging.getLogger(__name__)


class McpClient:
    """
    Synchronous MCP client.

    fastmcp is async-only, so all calls run on the shared async bridge loop.
    This keeps the persistent connection bound to a single event loop, regardless of the calling thread.
    """

    def __init__(self, server_name: str, server_config: dict):
        self.server_name = server_name
        self.server_config = server_config

        self._info = None
        self._connected = False
        self._connect_lock = asyncio.Lock()
        self._cache = {}  # cache for tools, prompt, resources
        self._client = self._init_client()

    def _init_client(self) -> Client:

        server_config = self.server_config.copy()
        mode = "auto"

        if server_config.get("legacy", False):
            mode = "legacy"
            del server_config["legacy"]

        logger.info(
            f"MCP {self.server_name}: Connecting to MCP server '{self.server_name}' mode: {mode}"
        )
        return Client(
            transport=MCPConfig(mcpServers={self.server_name: server_config}),
            mode=mode,
            init_timeout=MCP_INIT_TIMEOUT,
            progress_handler=self._progress_handler,
            message_handler=self._message_handler,
            log_handler=self._logging_handler,
        )

    async def _logging_handler(self, message: LogMessage):
        # logger.info(f"Logging message: {message}")
        # placeholder for later impl
        pass

    async def _message_handler(self, message) -> None:
        # print(message)
        # if hasattr(message, "root"):
        #     method = message.root.method
        #     print("MCP Received:", method)
        # placeholder for later impl
        pass

    async def _progress_handler(
        self, progress: float, total: float | None, message: str | None
    ) -> None:
        if total:
            print(f"{progress / total:6.1%}  {message or ''}")
        else:
            print(f"{progress}  {message or ''}")

    async def _ensure_connected(self):
        """Ensure the client connection is open, reusing an existing one if available."""
        async with self._connect_lock:
            if not self._connected:
                await self._client.__aenter__()
                self._connected = True
                logger.info(
                    f"MCP {self.server_name}: Opened persistent MCP connection for '{self.server_name}'"
                )

    async def _close(self):
        if self._connected:
            try:
                await self._client.__aexit__(None, None, None)
            except Exception:
                pass
            self._connected = False
            self._info = None
            logger.info(
                f"MCP {self.server_name}: Closed MCP connection for '{self.server_name}'"
            )

    async def _list(self, kind: str, fetch):
        await self._ensure_connected()
        if kind in self._cache:
            return self._cache[kind]
        items = await fetch()
        parsed = [item.model_dump() for item in items]
        self._cache[kind] = parsed
        return parsed

    async def _resource(self, resource_name: str):
        await self._ensure_connected()
        cache_key = f"resource:{resource_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]
        resource = await self._client.read_resource(resource_name)
        self._cache[cache_key] = resource
        return resource

    async def _call_tool(self, tool_name: str, args: dict) -> any:
        await self._ensure_connected()
        logger.info(
            f"MCP {self.server_name}: Calling tool '{tool_name}' with args {args}"
        )
        result = await self._client.call_tool_mcp(tool_name, arguments=args)
        logger.info(
            f"MCP {self.server_name}: Tool call result for '{tool_name}': {result}"
        )
        return result

    @property
    def client(self) -> Client:
        return self._client

    def close(self):
        """Close the persistent connection."""
        if self._connected:
            run_sync(self._close())

    def info(self) -> dict:
        if self._info is not None:
            return self._info

        info_dict = {
            "server_capabilities": self.list_server_capabilities(),
            "name": self.server_name,
            "tools": self.list_tools(),
            # "resources": self.list_resources(),
            # "prompts": self.list_prompts(),
        }
        self._info = info_dict
        return info_dict

    def list_server_capabilities(self) -> dict | None:
        run_sync(self._ensure_connected())
        data = self._client.server_capabilities
        if data is not None:
            return data.model_dump()
        return None

    def list_tools(self) -> list[Tool]:
        return run_sync(self._list("tools", self._client.list_tools))

    def list_resources(self) -> list[Resource]:
        return run_sync(self._list("resources", self._client.list_resources))

    def list_prompts(self) -> list[Prompt]:
        return run_sync(self._list("prompts", self._client.list_prompts))

    def call_tool(self, tool_name: str, args: dict) -> CallToolResult:
        return run_sync(self._call_tool(tool_name, args))

    def get_resource_content(self, resource_name: str) -> bytes | None:
        response: list = run_sync(self._resource(resource_name))
        if len(response) == 0:
            return None
        if len(response) >= 2:
            logger.warning(
                f"MCP {self.server_name}: Multi-part resource not supported. ({len(response)} parts detected)"
            )
            return None

        r = response[0]
        if isinstance(r, TextResourceContents):
            return r.text.encode("utf-8")
        elif isinstance(r, BlobResourceContents):
            return base64.b64decode(r.blob)
        return None

    def download_resource(
        self, resource_name: str, target_path: str, overwrite: bool = False
    ) -> None:
        response: list = run_sync(self._resource(resource_name))
        if len(response) == 0:
            raise Exception(f"Resource '{resource_name}' not found.")
        if len(response) >= 2:
            raise Exception(
                f"Multi-part resource not supported. ({len(response)} parts detected)"
            )

        if not target_path:
            raise Exception("Target path is required.")
        if os.path.exists(target_path) and not overwrite:
            raise Exception(f"Target path '{target_path}' already exists.")

        r = response[0]
        if isinstance(r, TextResourceContents):
            with open(target_path, "w") as f:
                f.write(r.text)
        elif isinstance(r, BlobResourceContents):
            with open(target_path, "wb") as f:
                base64str = r.blob
                f.write(base64.b64decode(base64str))
        else:
            raise TypeError(f"Unsupported resource type: {type(r)}")
