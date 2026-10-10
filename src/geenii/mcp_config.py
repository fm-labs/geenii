from pathlib import Path

import json

from geenii.config import MCP_CONFIG_FILE, GEENII_DIR, GEENII_WORKING_DIR
from geenii.mcp_client import McpClient

import logging

from geenii.utils.os_util import get_user_home_dir

logger = logging.getLogger(__name__)

config = None
_client_cache: dict[str, "McpClient"] = {}


def get_mcp_config(reload: bool = False):
    global config
    if config is None or reload:
        config = read_mcp_config_json()
    return config


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
    filenames = [
        Path(get_user_home_dir()) / ".geenii" / MCP_CONFIG_FILE,
        Path(GEENII_WORKING_DIR) / ".geenii" / MCP_CONFIG_FILE
    ]
    mcp_config = {"mcpServers": {}}
    for filename in filenames:
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
                mcp_config.update({
                    "mcpServers": data.get("mcpServers", {})
                })
        except FileNotFoundError:
            print(f"Configuration file {filename} not found.")
            #return {}
        except json.JSONDecodeError:
            print(f"Error decoding JSON from the file {filename}.")
            #return {}
    return mcp_config

# def write_mcp_config_json(data: dict):
#     """
#     Update the MCP configuration file with new data.
#
#     :param data: A dictionary containing the new configuration data.
#     """
#     filename = Path(GEENII_DIR) / MCP_CONFIG_FILE
#     try:
#         with open(filename, 'w') as f:
#             json.dump(data, f, indent=4)
#         print(f"Configuration file {filename} updated successfully.")
#     except Exception as e:
#         print(f"Error updating configuration file {filename}: {e}")



