from __future__ import annotations

import asyncio
import datetime
from typing import Any

from geenii.core.tools import geenii_tools
from geenii.mcp import get_mcp_config, McpClient
from geenii.tool.registry import PythonTool, ToolRegistry, logger
from geenii.utils.cached import cached

TOOLS: ToolRegistry | None = None


def get_default_tool_registry() -> ToolRegistry:
    global TOOLS
    if TOOLS is None:
        TOOLS = init_default_tool_registry()
    return TOOLS


def init_default_tool_registry():
    registry = ToolRegistry()
    init_builtin_tools(registry)
    init_mcp_server_tools_sync(registry)
    return registry


def init_builtin_tools(registry: ToolRegistry):
    for name, tool in geenii_tools._tools.items():
        registry.register(tool)

    registry.register(PythonTool(
        name="calculate_square_root",
        description="Calculate the square root of a number.",
        parameters={
            "type": "object",
            "properties": {
                "number": {"type": "number", "description": "The number to calculate the square root of."}
            },
            "required": ["number"]
        },
        handler=lambda number: number ** 0.5
    ))

    registry.register(PythonTool(
        name="get_current_time",
        description="Get the current UTC system time.",
        parameters={
            "type": "object",
            "properties": {}
        },
        handler=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat()
    ))

async def init_mcp_server_tools(registry: ToolRegistry):
    # mcp_servers = {
    #     "duckduckgo": {
    #         "command": "docker",
    #         "args": [
    #             "run",
    #             "-i",
    #             "--rm",
    #             "mcp/duckduckgo"
    #         ]
    #     }
    # }
    mcp_config = get_mcp_config()
    if not mcp_config or "mcpServers" not in mcp_config:
        print("No MCP servers configured")
        return

    @cached(ttl=3600)
    async def read_mcp_server_tools(server_name, server_conf) -> list[dict]:
        try:
            mcp_client = McpClient(server_name, server_conf)
            try:
                tools = await mcp_client.list_tools()
            except Exception as e:
                # try again after a short delay in case the server is still starting up
                print(f"Error listing tools from MCP server {server_name}: {e}. Retrying in 1 seconds...")
                try:
                    await asyncio.sleep(1)
                    tools = await mcp_client.list_tools()
                except Exception as e:
                    print(f"Error listing tools from MCP server {server_name} on second attempt: {e}. Skipping this server.")
                    return []

            return tools
        except Exception as e:
            print(f"Error retrieving tools from MCP server {server_name}: {e}")
            return []

    for server_name, server_conf in mcp_config["mcpServers"].items():
        try:
            mcp_tools = await read_mcp_server_tools(server_name, server_conf)

            # map the MCP tool definitions to the internal tool representation and register them in the registry
            registry.register_mcp_tools(
                mcp_server_id=server_name,
                tool_definitions=mcp_tools
            )
        except Exception as e:
            print(f"Error connecting to MCP server {server_name}: {e}")
            continue

def init_mcp_server_tools_sync(registry: ToolRegistry):
    # wrapper for the async version of init_mcp_server_tools to be used in synchronous contexts
    #asyncio.run(init_mcp_server_tools(registry))
    async def initialize():
        await init_mcp_server_tools(registry)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(initialize())


async def execute_tool_call(registry: ToolRegistry, tool_name: str, args: dict[str,Any], **kwargs) -> Any:
    """Look up and execute a tool by name and given arguments."""
    tool = registry.get(tool_name)
    if tool is None:
        raise ValueError(f"Tool {tool_name!r} is not registered")
    logger.info(f'EXECUTING TOOL "{tool_name}" with args {args}')
    return await tool.invoke(args=args, **kwargs)


def execute_tool_call_sync(registry: ToolRegistry, tool_name: str, args: dict[str,Any], **kwargs) -> Any:
    """Synchronous wrapper around execute_tool_call."""
    return asyncio.run(execute_tool_call(registry, tool_name, args, **kwargs))
