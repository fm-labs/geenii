import asyncio
import json
from pathlib import Path

from fastmcp import Client
from fastmcp.mcp_config import MCPConfig
from fastmcp.prompts import Prompt

from geenii.config import MCP_CONFIG_FILE, DATA_DIR

config = None
client = None


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
    Get an MCP client for a specific server.

    :param server_name: The name of the MCP server.
    :return: An MCP Client instance for the specified server.
    """
    server_config = get_mcp_config_for_server(server_name)
    if server_config is None:
        raise ValueError(f"MCP server '{server_name}' not found in configuration.")

    mcp_client = McpClient(server_name, server_config)
    return mcp_client


def read_mcp_config_json() -> dict:
    """
    Read a configuration file and return its contents as a dictionary.

    :return: A dictionary containing the configuration data.
    """
    filename = Path(DATA_DIR) / MCP_CONFIG_FILE
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
    filename = Path(DATA_DIR) / MCP_CONFIG_FILE
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

    async def get_info(self) -> dict:

        if self._info is not None:
            return self._info

        async with self.client:
            try:
                # initialize_result = await client.initialize_result
                tools = await self.client.list_tools()
                resources = await self.client.list_resources()
                prompts: list[Prompt] = await self.client.list_prompts()

                info_dict = {
                    "name": self.server_name,
                    "status": "connected",
                    # "message": f"Connected to MCP server '{server_name}' successfully.",
                    # "initialize_result": initialize_result.model_dump(),
                    "tools": [tool.model_dump() for tool in tools],
                    "resources": [res.model_dump() for res in resources],
                    "prompts": [prompt.model_dump() for prompt in prompts],
                }
                print(info_dict)
                #return MCPServerInfo(**info_dict)
                self._info = info_dict
                return info_dict
            except Exception as e:
                raise

    async def list_tools(self):
        info = await self.get_info()
        return info["tools"]

    async def list_resources(self):
        info = await self.get_info()
        return info["resources"]

    async def list_prompts(self):
        info = await self.get_info()
        return info["prompts"]

    def list_tools_sync(self):
        # This is a synchronous wrapper around the asynchronous list_tools method.
        #loop = asyncio.get_event_loop()
        #return loop.run_until_complete(self.list_tools())
        return asyncio.run(self.list_tools())

    async def call_tool(self, tool_name: str, args: dict) -> any:
        async with self.client:
            try:
                #result = await self.client.call_tool(tool_name, arguments=args)
                result = await self.client.call_tool_mcp(tool_name, arguments=args)
                print("Tool call result:", result)
                return result
            except Exception as e:
                raise

    def call_tool_sync(self, tool_name: str, args: dict) -> any:
        print(f"Calling tool {tool_name} with args {args} on MCP server {self.server_name}")
        import asyncio
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(self.call_tool(tool_name, args))