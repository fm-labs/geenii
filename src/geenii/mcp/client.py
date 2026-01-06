import json
from pathlib import Path

from fastmcp import Client

from geenii.settings import MCP_CONFIG_FILE, DATA_DIR

config = None
client = None


def get_mcp_config(reload: bool = False):
    global config
    if config is None or reload:
        config = read_mcp_config_json()
    return config


def get_mcp_client():
    global client
    if client is None:
        _config = get_mcp_config()
        client = Client(_config)
    return client

def get_mcp_config_for_server(server_name: str) -> dict | None:
    """
    Get the configuration for a specific MCP server.

    :param server_name: The name of the MCP server.
    :return: A dictionary containing the configuration for the specified server.
    """
    _config = get_mcp_config()
    if "mcpServers" in _config:
        for server in _config["mcpServers"]:
            if server.get("name") == server_name:
                return server
    return None

def get_mcp_client_for_server(server_name: str) -> Client:
    """
    Get an MCP client for a specific server.

    :param server_name: The name of the MCP server.
    :return: An MCP Client instance for the specified server.
    """
    _config = get_mcp_config()
    # if "mcpServers" not in _config or server_name not in _config["mcpServers"]:
    #     raise ValueError(f"MCP server '{server_name}' not found in configuration.")
    #
    # server_config = {
    #     "mcpServers": {
    #         server_name: _config["mcpServers"][server_name]
    #     }
    # }
    # return Client(server_config)
    if "mcpServers" in _config:
        for server in _config["mcpServers"]:
            if server.get("name") == server_name:
                server_config = {
                    "mcpServers": {
                        server_name: {
                            "name": server.get("name"),
                            "url": server.get("url"),
                            "command": server.get("command"),
                            "args": server.get("args", []),
                            "env": server.get("env", {}),
                        }
                    }
                }
                print(server_config)
                return Client(server_config)
    raise ValueError(f"MCP server '{server_name}' not found in configuration.")


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