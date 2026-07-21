from __future__ import annotations

import asyncio

from geenii.core.tools import init_core_tools
from geenii.mcp_helper import get_mcp_config, McpClient
from geenii.pm.process_manager_client import ProcessManagerClient
from geenii.tool.computer import ComputerTool
from geenii.tool.registry import ToolRegistry
from geenii.utils.cached import cached

_pm_client = ProcessManagerClient()


def init_builtin_tools(registry: ToolRegistry):
    registry.register(ComputerTool(
        name="bash",
        description="Execute a shell command on the local machine and return its output.",
        parameters={
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
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "The python command to execute without the binary name, e.g. '-m mymodule script.py'."}
            },
            "required": ["command"]
        },
    ))
    # registry.register(SandboxTool(
    #     name="sandbox_python",
    #     description="Execute a Python command inside a sandboxed Docker container. "
    #                 "The container runs with no network, read-only filesystem, dropped capabilities, "
    #                 "and strict resource limits. Requires a skill to be selected (SKILL_DIR is used as the app directory).",
    #     parameters={
    #         "type": "object",
    #         "properties": {
    #             "command": {"type": "string", "description": "The command to run inside the container, e.g. 'python3 scripts/fetch.py --format json'."}
    #         },
    #         "required": ["command"]
    #     },
    #     runtime="python",
    # ))
    # registry.register(SandboxTool(
    #     name="sandbox_bash",
    #     description="Execute a shell command inside a sandboxed Docker container. "
    #                 "The container runs with no network, read-only filesystem, dropped capabilities, "
    #                 "and strict resource limits. Requires a skill to be selected (SKILL_DIR is used as the app directory).",
    #     parameters={
    #         "type": "object",
    #         "properties": {
    #             "command": {"type": "string", "description": "The shell command to run inside the container, e.g. 'ls -la /app'."}
    #         },
    #         "required": ["command"]
    #     },
    #     runtime="bash",
    # ))
    init_core_tools(registry)
    #init_process_tools(registry, _pm_client)

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


async def init_mcp_server_tools(registry: ToolRegistry, server_names: set[str] = None):
    mcp_config = get_mcp_config()
    if not mcp_config or "mcpServers" not in mcp_config:
        print("No MCP servers configured")
        return

    for server_name, server_conf in mcp_config["mcpServers"].items():
        if server_names is not None and server_name not in server_names:
            continue

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

# def init_mcp_server_tools_sync(registry: ToolRegistry):
#     # wrapper for the async version of init_mcp_server_tools to be used in synchronous contexts
#     #asyncio.run(init_mcp_server_tools(registry))
#     async def initialize():
#         await init_mcp_server_tools(registry)
#
#     loop = asyncio.get_event_loop()
#     loop.run_until_complete(initialize())


# async def execute_tool_call(registry: ToolRegistry, tool_name: str, args: dict[str,Any], **kwargs) -> Any:
#     """Look up and execute a tool by name and given arguments."""
#     tool = registry.get(tool_name)
#     if tool is None:
#         raise ValueError(f"Tool {tool_name!r} is not registered")
#     return await tool.invoke(args=args, **kwargs)
#
#
# def execute_tool_call_sync(registry: ToolRegistry, tool_name: str, args: dict[str,Any], **kwargs) -> Any:
#     """Synchronous wrapper around execute_tool_call."""
#     return asyncio.run(execute_tool_call(registry, tool_name, args, **kwargs))
