import asyncio

from fastmcp import Client
from fastmcp.mcp_config import MCPConfig
from fastmcp.prompts import Prompt

from geenii.config import MCP_INIT_TIMEOUT
from geenii.utils.async_bridge import run_sync

import logging
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
        self.client = Client(transport=MCPConfig(mcpServers={server_name: server_config}), init_timeout=MCP_INIT_TIMEOUT)
        self._info = None
        self._connected = False
        self._connect_lock = asyncio.Lock()
        self._cache = {} # cache for tools, prompt, resources

    async def _ensure_connected(self):
        """Ensure the client connection is open, reusing an existing one if available."""
        async with self._connect_lock:
            if not self._connected:
                await self.client.__aenter__()
                self._connected = True
                logger.info(f"Opened persistent MCP connection for '{self.server_name}'")

    async def _close(self):
        if self._connected:
            try:
                await self.client.__aexit__(None, None, None)
            except Exception:
                pass
            self._connected = False
            self._info = None
            logger.info(f"Closed MCP connection for '{self.server_name}'")

    async def _list(self, kind: str, fetch):
        await self._ensure_connected()
        if kind in self._cache:
            return self._cache[kind]
        items = await fetch()
        parsed = [item.model_dump() for item in items]
        self._cache[kind] = parsed
        return parsed

    async def _call_tool(self, tool_name: str, args: dict) -> any:
        await self._ensure_connected()
        logger.info(f"Calling tool '{tool_name}' with args {args}")
        result = await self.client.call_tool_mcp(tool_name, arguments=args)
        logger.info(f"Tool call result for '{tool_name}' on '{self.server_name}': {result}")
        return result

    def close(self):
        """Close the persistent connection."""
        if self._connected:
            run_sync(self._close())

    def info(self) -> dict:
        if self._info is not None:
            return self._info

        tools = self.list_tools()
        resources = self.list_resources()
        prompts: list[Prompt] = self.list_prompts()

        info_dict = {
            "name": self.server_name,
            "tools": tools,
            "resources": resources,
            "prompts": prompts,
        }
        self._info = info_dict
        return info_dict

    def list_tools(self):
        return run_sync(self._list("tools", self.client.list_tools))

    def list_resources(self):
        return run_sync(self._list("resources", self.client.list_resources))

    def list_prompts(self):
        return run_sync(self._list("prompts", self.client.list_prompts))

    def call_tool(self, tool_name: str, args: dict) -> any:
        return run_sync(self._call_tool(tool_name, args))
