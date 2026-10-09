from fastmcp import Client
from fastmcp.mcp_config import MCPConfig
from fastmcp.prompts import Prompt

from geenii.config import MCP_INIT_TIMEOUT

import logging
logger = logging.getLogger(__name__)


class McpClient:

    def __init__(self, server_name: str, server_config: dict):
        self.server_name = server_name
        self.server_config = server_config
        self.client = Client(transport=MCPConfig(mcpServers={server_name: server_config}), init_timeout=MCP_INIT_TIMEOUT)
        self._info = None
        self._connected = False
        self._cache = {} # cache for tools, prompt, resources

    async def _ensure_connected(self):
        """Ensure the client connection is open, reusing an existing one if available."""
        if not self._connected:
            await self.client.__aenter__()
            self._connected = True
            logger.info(f"Opened persistent MCP connection for '{self.server_name}'")

    async def close(self):
        """Close the persistent connection."""
        if self._connected:
            try:
                await self.client.__aexit__(None, None, None)
            except Exception:
                pass
            self._connected = False
            self._info = None
            logger.info(f"Closed MCP connection for '{self.server_name}'")

    async def info(self) -> dict:
        if self._info is not None:
            return self._info

        tools = await self.list_tools()
        resources = await self.list_resources()
        prompts: list[Prompt] = await self.list_prompts()

        info_dict = {
            "name": self.server_name,
            "tools": tools,
            "resources": resources,
            "prompts": prompts,
        }
        self._info = info_dict
        return info_dict

    async def list_tools(self):
        await self._ensure_connected()
        if "tools" in self._cache:
            return self._cache["tools"]
        tools = await self.client.list_tools()
        parsed = [tool.model_dump() for tool in tools]
        self._cache["tools"] = parsed
        return parsed

    async def list_resources(self):
        await self._ensure_connected()
        if "resources" in self._cache:
            return self._cache["resources"]
        resources = await self.client.list_resources()
        parsed = [resource.model_dump() for resource in resources]
        self._cache["resources"] = parsed
        return parsed

    async def list_prompts(self):
        await self._ensure_connected()
        if "prompts" in self._cache:
            return self._cache["prompts"]
        prompts = await self.client.list_prompts()
        parsed = [prompt.model_dump() for prompt in prompts]
        self._cache["prompts"] = parsed
        return parsed

    async def call_tool(self, tool_name: str, args: dict) -> any:
        await self._ensure_connected()
        logger.info(f"Calling tool '{tool_name}' with args {args}")
        result = await self.client.call_tool_mcp(tool_name, arguments=args)
        logger.info(f"Tool call result for '{tool_name}' on '{self.server_name}': {result}")
        return result
