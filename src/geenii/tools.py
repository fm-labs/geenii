from __future__ import annotations

import dataclasses
import logging
import time
import traceback
from datetime import datetime
from pathlib import Path

from geenii.config import GEENII_CACHE_DIR, GEENII_WORKING_DIR
from geenii.core.tools import init_core_os_tools
from geenii.mcp_client import McpClient
from geenii.mcp_config import get_mcp_config, get_mcp_config_for_server
from geenii.tool.common import Tool, ToolCallContext, ToolCallResult
from geenii.tool.computer import ComputerTool, ReadTool, WriteTool
from geenii.tool.registry import ToolRegistry
from geenii.tool.webtools import WebFetchTool
from geenii.utils.cached import cached
from geenii.utils.json_util import append_jsonl

logger = logging.getLogger(__name__)


def init_builtin_os_tools(registry: ToolRegistry):
    init_core_os_tools(registry)

    registry.register(ReadTool())
    registry.register(WriteTool())
    registry.register(
        ComputerTool(
            name="bash",
            description="Execute a shell command on the local machine and return its output.",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The shell command to execute. The command must be a single-line string, e.g. 'ls -la /tmp'.",
                    }
                },
                "required": ["command"],
            },
        )
    )
    registry.register(
        ComputerTool(
            name="python",
            description="Execute a python script and return its output.",
            input_schema={
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "The python command to execute without the binary name, e.g. '-m mymodule script.py'.",
                    }
                },
                "required": ["command"],
            },
            command_template="python3 {command}",
        )
    )

def init_builtin_webtools(registry: ToolRegistry):
    registry.register(WebFetchTool())



# empty results are not cached: a server that is still starting up may list no tools yet
@cached(ttl=3600, cache_if=bool)
def read_mcp_server_tools(server_name) -> list[dict]:
    """List the tools of an MCP server. Raises if the server is not configured or can't be reached."""
    # short-lived client for discovery only; tool calls use the cached client from get_mcp_client_for_server
    server_conf = get_mcp_config_for_server(server_name, compile=True)
    if server_conf is None:
        raise ValueError(f"MCP server '{server_name}' is not configured")
    mcp_client = McpClient(server_name, server_conf)
    try:
        try:
            return mcp_client.list_tools()
        except Exception as e:
            # try again after a short delay in case the server is still starting up
            logger.warning(f"Error listing tools from MCP server {server_name}: {e}. Retrying in 1 seconds...")
            time.sleep(1)
            return mcp_client.list_tools()
    finally:
        mcp_client.close()


def init_mcp_server_tools(
    registry: ToolRegistry,
    server_names: set[str] | None = None,
    timeout: float | None = None,
):
    """Register the tools of the given MCP servers (default: all configured), waiting for their discovery.

    Discovery runs in parallel and is shared with any other caller loading the same servers. A server that
    fails, or is not loaded within `timeout` seconds, is skipped.
    """
    # imported here: the loader imports this module
    from geenii.mcp_loader import get_mcp_loader

    get_mcp_loader().register_into(registry, server_names, timeout=timeout)


def invoke_tool(
    tool: Tool,
    args: dict[str, str],
    env: dict,
    cwd: str | None = None,
    caller_id: str = "anonymous",
    secret_keys: set[str] | None = None,
) -> ToolCallResult:
    """`secret_keys` are env vars whose values are redacted in the logs, on top of the name-based redaction."""
    result = None
    cwd = cwd or GEENII_WORKING_DIR
    ctx = ToolCallContext(cwd=cwd, caller_id=caller_id)
    try:
        logger.info(
            f"Invoking tool {tool.name} with args: {args}, env: {_redact_env_vars(env, secret_keys)}, cwd: {cwd}, tool_ctx_id: {ctx.id}"
        )
        result = tool.invoke(args=args, env=env, ctx=ctx)
        logger.info(f"Tool result for {tool.name}, tool_ctx_id: {ctx.id}: {result}")
        return result
    except Exception as e:
        logger.error(f"Error executing tool {tool.name}, tool_ctx_id: {ctx.id}: {e}")
        # traceback.print_exc()
        result = e
        raise e from e
    finally:
        _log_tool_call(
            tool.name,
            args,
            _redact_env_vars(env, secret_keys),
            cwd,
            caller_id=caller_id,
            result=result,
        )


# matched anywhere in a name
_SENSITIVE_KEYS = ("password", "secret", "api_key", "token")
# matched only as a whole `_`-separated part of a name, so that e.g. PATH or PATTERN are not redacted
_SENSITIVE_NAME_PARTS = ("pass", "passwd", "pat")


def _is_sensitive_env_var(name: str) -> bool:
    name = name.lower()
    return any(s in name for s in _SENSITIVE_KEYS) or any(p in _SENSITIVE_NAME_PARTS for p in name.split("_"))


def _redact_env_vars(env_vars: dict[str, str], secret_keys: set[str] | None = None) -> dict[str, str]:
    """A copy of env_vars with sensitive values redacted. The input is left untouched, since it is passed on to the tool."""
    secret_keys = secret_keys or set()
    return {k: "REDACTED" if k in secret_keys or _is_sensitive_env_var(k) else v for k, v in env_vars.items()}


def _log_tool_call(
    tool_name,
    args: dict[str, str],
    env: dict[str, str],
    cwd: str | None,
    caller_id: str,
    result: ToolCallResult | Exception | None = None,
):

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
    append_jsonl(
        log_file,
        {
            "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S"),
            "caller_id": caller_id,
            "tool": tool_name,
            "args": args,
            "env": env,
            "cwd": cwd,
            "result": result,
        },
    )
