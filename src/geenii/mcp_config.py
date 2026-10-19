from pathlib import Path

import atexit
import copy
import json
import os
import re

from geenii.config import MCP_CONFIG_FILE, GEENII_WORKING_DIR
from geenii.mcp_client import McpClient

import logging

from geenii.utils.os_util import get_user_home_dir

logger = logging.getLogger(__name__)

config = None
_client_cache: dict[str, "McpClient"] = {}


def get_mcp_config(reload: bool = False):
    global config
    if config is None or reload:
        config = read_mcp_config_files()
    return config


def get_mcp_config_for_server(server_name: str, compile: bool = False) -> dict | None:
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

    server_conf = _config["mcpServers"][server_name]
    if compile:
        server_conf = _expand_env_vars_in_server_config(
            copy.deepcopy(server_conf), dict(**_config.get("env", {}))
        )
    return server_conf


def get_mcp_client_for_server(server_name: str) -> "McpClient":
    """
    Get a cached MCP client for a specific server. Reuses existing clients
    so that connections/handshakes are not repeated on every tool call.

    :param server_name: The name of the MCP server.
    :return: An MCP Client instance for the specified server.
    """
    if server_name in _client_cache:
        logger.warning(f"Using cached MCP client for server '{server_name}'")
        return _client_cache[server_name]

    server_config = get_mcp_config_for_server(server_name, compile=True)
    if server_config is None:
        raise ValueError(f"MCP server '{server_name}' not found in configuration.")

    mcp_client = McpClient(server_name, server_config)
    _client_cache[server_name] = mcp_client
    logger.info(f"Created and cached MCP client for server '{server_name}'")
    return mcp_client


def _expand_env_vars_in_server_config(
    server_config: dict, env_vars: dict[str, str]
) -> dict:

    def expand_env_vars(q: str | None, env_vars: dict) -> str | None:
        """replace all occurences of ${ENV_VAR} with their respective values.}"""
        if q is None:
            return None

        # unknown variables are left untouched
        return re.sub(
            r"\$\{(\w+)\}", lambda m: str(env_vars.get(m.group(1), m.group(0))), q
        )

    # replace in strings
    for loc in ["command", "url"]:
        if isinstance(server_config.get(loc), str):
            server_config[loc] = expand_env_vars(server_config[loc], env_vars)

    # replace in lists of strings
    for loc in ["args"]:
        if isinstance(server_config.get(loc), list):
            server_config[loc] = [
                expand_env_vars(v, env_vars) if isinstance(v, str) else v
                for v in server_config[loc]
            ]

    # replace in dict[str,str]
    for loc in ["env", "headers"]:
        if isinstance(server_config.get(loc), dict):
            server_config[loc] = {
                k: expand_env_vars(v, env_vars) if isinstance(v, str) else v
                for k, v in server_config[loc].items()
            }

    return server_config


def close_mcp_clients():
    """Close all cached MCP clients."""
    while _client_cache:
        server_name, client = _client_cache.popitem()
        try:
            client.close()
        except Exception as e:
            logger.warning(f"Error closing MCP client for server '{server_name}': {e}")


# registered after the async bridge's own atexit hook, so it runs before the bridge loop is stopped
atexit.register(close_mcp_clients)


def get_root_mcp_config_path() -> Path:
    """The user-level mcp.json; the base config that the working dir mcp.json overrides."""
    return Path(get_user_home_dir()) / ".geenii" / MCP_CONFIG_FILE


def get_mcp_config_paths() -> list[Path]:
    """All mcp.json files, in the order they are merged (later files win)."""
    return [
        get_root_mcp_config_path(),
        Path(GEENII_WORKING_DIR) / ".geenii" / MCP_CONFIG_FILE,
    ]


def read_mcp_config_files() -> dict:
    """
    Read a configuration file and return its contents as a dictionary.

    :return: A dictionary containing the configuration data.
    """
    servers: dict = {}
    env: dict = {}
    for filename in get_mcp_config_paths():
        try:
            with open(filename, "r") as f:
                data = json.load(f)
                servers.update(data.get("mcpServers", {}))
                env.update(data.get("env", {}))
        except FileNotFoundError:
            logger.warning(f"Configuration file {filename} not found.")
        except json.JSONDecodeError:
            logger.error(f"Error decoding JSON from the file {filename}.")
    return {"mcpServers": servers, "env": env}


def read_root_mcp_config() -> dict:
    """Read the root mcp.json as-is. A missing file reads as an empty config."""
    path = get_root_mcp_config_path()
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not contain a JSON object.")
    data.setdefault("mcpServers", {})
    return data


def write_root_mcp_config(data: dict) -> None:
    """Write the root mcp.json atomically, then reload the merged config."""
    path = get_root_mcp_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.name + ".tmp")
    with open(tmp_path, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
    os.replace(tmp_path, path)
    get_mcp_config(reload=True)


def _drop_cached_client(server_name: str) -> None:
    """Close the cached client of a server, so the next use connects with the new config."""
    client = _client_cache.pop(server_name, None)
    if client is not None:
        try:
            client.close()
        except Exception as e:
            logger.warning(f"Error closing MCP client for server '{server_name}': {e}")


def save_mcp_server_config(server_name: str, server_config: dict) -> None:
    """Add or replace a server entry in the root mcp.json."""
    data = read_root_mcp_config()
    data["mcpServers"][server_name] = server_config
    write_root_mcp_config(data)
    _drop_cached_client(server_name)


def delete_mcp_server_config(server_name: str) -> bool:
    """Remove a server entry from the root mcp.json. Returns False if the root file has no such server."""
    data = read_root_mcp_config()
    if server_name not in data["mcpServers"]:
        return False
    del data["mcpServers"][server_name]
    write_root_mcp_config(data)
    _drop_cached_client(server_name)
    return True
