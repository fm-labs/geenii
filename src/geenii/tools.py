from __future__ import annotations

import dataclasses
import time
import traceback
from datetime import datetime
from pathlib import Path

from geenii.config import GEENII_CACHE_DIR
from geenii.core.tools import init_core_tools
from geenii.mcp_client import McpClient
from geenii.mcp_config import get_mcp_config, get_mcp_config_for_server
from geenii.tool.common import ToolCallResult, Tool
from geenii.tool.computer import ComputerTool
from geenii.tool.registry import ToolRegistry
from geenii.utils.cached import cached
from geenii.utils.json_util import append_jsonl

import logging
logger = logging.getLogger(__name__)

def init_builtin_tools(registry: ToolRegistry):
    registry.register(ComputerTool(
        name="bash",
        description="Execute a shell command on the local machine and return its output.",
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The shell command to execute. The command must be a single-line string, e.g. 'ls -la /tmp'."}
            },
            "required": ["command"]
        },
    ))
    registry.register(ComputerTool(
        name="python",
        description="Execute a python script and return its output.",
        input_schema={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The python command to execute without the binary name, e.g. '-m mymodule script.py'."}
            },
            "required": ["command"]
        },
        command_template="python3 {command}",
    ))
    init_core_tools(registry)


# empty results are not cached: [] is also what a failed listing returns, and it would hide the server's tools for the full ttl
@cached(ttl=3600, cache_if=bool)
def read_mcp_server_tools(server_name) -> list[dict]:
    # short-lived client for discovery only; tool calls use the cached client from get_mcp_client_for_server
    server_conf = get_mcp_config_for_server(server_name, compile=True)
    if server_conf is None:
        logger.warning(f"No MCP servers configured for server '{server_name}'")
        return []
    mcp_client = McpClient(server_name, server_conf)
    try:
        try:
            tools = mcp_client.list_tools()
        except Exception as e:
            # try again after a short delay in case the server is still starting up
            logger.warning(f"Error listing tools from MCP server {server_name}: {e}. Retrying in 1 seconds...")
            try:
               time.sleep(1)
               tools = mcp_client.list_tools()
            except Exception as e:
               logger.error(f"Error listing tools from MCP server {server_name} on second attempt: {e}. Skipping this server.")
               return []
            #logger.error(f"Error listing tools from MCP server {server_name}: {e}.")
            #return []
        return tools
    except Exception as e:
        logger.error(f"Error retrieving tools from MCP server {server_name}: {e}")
        return []
    finally:
        mcp_client.close()


def init_mcp_server_tools(registry: ToolRegistry, server_names: set[str] = None):
    mcp_config = get_mcp_config()
    if not mcp_config or "mcpServers" not in mcp_config:
        logger.warning("No MCP servers configured")
        return

    for server_name, _ in mcp_config["mcpServers"].items():
        if server_names is not None and server_name not in server_names:
            continue

        try:
            mcp_tools = read_mcp_server_tools(server_name)
            if len(mcp_tools) > 0:
                # map the MCP tool definitions to the internal tool representation and register them in the registry
                registry.register_mcp_tools(
                    mcp_server_id=server_name, tool_definitions=mcp_tools
                )
        except Exception as e:
            logger.error(f"Error connecting to MCP server {server_name}: {e}")
            continue
            

def invoke_tool(tool: Tool, args: dict[str, str], env: dict, cwd: str | None = None, caller_id: str = "anonymous",
                secret_keys: set[str] | None = None) -> ToolCallResult:
    """`secret_keys` are env vars whose values are redacted in the logs, on top of the name-based redaction."""
    result = None
    try:
        logger.info(f"Invoking tool {tool.name} with args: {args}, env: {_redact_env_vars(env, secret_keys)}, cwd: {cwd}")
        result = tool.invoke(args=args, env=env, cwd=cwd)
        logger.info(f"Tool result for {tool.name}: {result}")
        return result
    except Exception as e:
        logger.error(f"Error executing tool {tool.name}: {e}")
        # traceback.print_exc()
        result = e
        raise e from e
    finally:
        _log_tool_call(tool.name, args, _redact_env_vars(env, secret_keys), cwd, caller_id=caller_id, result=result)


_SENSITIVE_KEYS = ("password", "secret", "api_key", "token", "pass", "pat")

def _redact_env_vars(env_vars: dict[str, str], secret_keys: set[str] | None = None) -> dict[str, str]:
    """A copy of env_vars with sensitive values redacted. The input is left untouched, since it is passed on to the tool."""
    secret_keys = secret_keys or set()
    return {k: "REDACTED" if k in secret_keys or any(s in k.lower() for s in _SENSITIVE_KEYS) else v
            for k, v in env_vars.items()}

def _log_tool_call(tool_name, args: dict[str, str],
                   env: dict[str, str],
                   cwd: str | None,
                   caller_id: str,
                   result: ToolCallResult | Exception | None = None):

    now = datetime.now()
    date_formatted = now.strftime("%Y-%m-%d")
    log_file = f"{GEENII_CACHE_DIR}/logs/tool-use-{date_formatted}.log"
    Path(log_file).parent.mkdir(parents=True, exist_ok=True)

    if isinstance(result, ToolCallResult):
        result = dataclasses.asdict(result)
    if isinstance(result, Exception):
        result = {
            "exception": str(result),
            "traceback": traceback.format_exc(),
        }
    append_jsonl(log_file, {
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S"),
        "caller_id": caller_id,
        "tool": tool_name,
        "args": args,
        "env": env,
        "cwd": cwd,
        "result": result,
    })