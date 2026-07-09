from pathlib import Path

import json
from fastmcp import Client
from fastmcp.mcp_config import MCPConfig
from fastmcp.prompts import Prompt

from geenii.config import MCP_CONFIG_FILE, GEENII_DIR

import logging

logger = logging.getLogger(__name__)

config = None
_client_cache: dict[str, "McpClient"] = {}


def get_mcp_config(reload: bool = False):
    global config
    if config is None or reload:
        config = read_mcp_config_json()
    return config


# def get_mcp_client():
#     global client
#     if client is None:
#         _config = get_mcp_config()
#         client = Client(_config)
#     return client

def get_mcp_config_for_server(server_name: str) -> dict | None:
    """
    Get the configuration for a specific MCP server.

    :param server_name: The name of the MCP server.
    :return: A dictionary containing the configuration for the specified server.
    """
    _config = get_mcp_config()

    # get the server configuration for the specified server name
    if "mcpServers" not in _config or server_name not in _config["mcpServers"]:
        # raise ValueError(f"MCP server '{server_name}' not found in configuration.")
        return None

    return _config["mcpServers"][server_name]

def get_mcp_client_for_server(server_name: str) -> "McpClient":
    """
    Get a cached MCP client for a specific server. Reuses existing clients
    so that connections/handshakes are not repeated on every tool call.

    :param server_name: The name of the MCP server.
    :return: An MCP Client instance for the specified server.
    """
    if server_name in _client_cache:
        return _client_cache[server_name]

    server_config = get_mcp_config_for_server(server_name)
    if server_config is None:
        raise ValueError(f"MCP server '{server_name}' not found in configuration.")

    mcp_client = McpClient(server_name, server_config)
    _client_cache[server_name] = mcp_client
    logger.info(f"Created and cached MCP client for server '{server_name}'")
    return mcp_client


def read_mcp_config_json() -> dict:
    """
    Read a configuration file and return its contents as a dictionary.

    :return: A dictionary containing the configuration data.
    """
    filename = Path(GEENII_DIR) / MCP_CONFIG_FILE
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Configuration file {filename} not found.")
        return {}
    except json.JSONDecodeError:
        print(f"Error decoding JSON from the file {filename}.")
        return {}


def write_mcp_config_json(data: dict):
    """
    Update the MCP configuration file with new data.

    :param data: A dictionary containing the new configuration data.
    """
    filename = Path(GEENII_DIR) / MCP_CONFIG_FILE
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"Configuration file {filename} updated successfully.")
    except Exception as e:
        print(f"Error updating configuration file {filename}: {e}")



class McpClient:

    def __init__(self, server_name: str, server_config: dict):
        self.server_name = server_name
        self.server_config = server_config
        self.client = Client(transport=MCPConfig(mcpServers={server_name: server_config}))
        self._info = None
        self._connected = False

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

    async def get_info(self) -> dict:
        if self._info is not None:
            return self._info

        await self._ensure_connected()
        tools = await self.client.list_tools()
        resources = await self.client.list_resources()
        prompts: list[Prompt] = await self.client.list_prompts()

        info_dict = {
            "name": self.server_name,
            "status": "connected",
            "tools": [tool.model_dump() for tool in tools],
            "resources": [res.model_dump() for res in resources],
            "prompts": [prompt.model_dump() for prompt in prompts],
        }
        self._info = info_dict
        return info_dict

    async def list_tools(self):
        info = await self.get_info()
        return info["tools"]

    async def list_resources(self):
        info = await self.get_info()
        return info["resources"]

    async def list_prompts(self):
        info = await self.get_info()
        return info["prompts"]

    async def call_tool(self, tool_name: str, args: dict) -> any:
        await self._ensure_connected()
        result = await self.client.call_tool_mcp(tool_name, arguments=args)
        logger.info(f"Tool call result for '{tool_name}' on '{self.server_name}': {result}")
        return result