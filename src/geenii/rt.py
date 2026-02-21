from __future__ import annotations

from geenii.core.core_tools import geenii_tools
from geenii.mcp.client import get_mcp_config, McpClient
from geenii.tools import PythonTool, ToolRegistry
from geenii.utils.cached import cached

TOOLS: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    global TOOLS
    if TOOLS is None:
        TOOLS = init_tool_registry()
    return TOOLS


def init_tool_registry():
    # todo: load built-in tools and register them in the registry
    # todo: load tools from config file or database
    # todo: support dynamic loading of tools from plugins or external sources
    # todo: implement caching and efficient lookup of tools in the registry
    # todo: implement tool policies and access control in the registry
    registry = ToolRegistry()
    init_builtin_tools(registry)
    init_mcp_server_tools(registry)

    return registry


async def init_builtin_tools(registry: ToolRegistry):
    # registry.register(PythonTool(
    #     name="file_exists",
    #     description="Check if a file exists at the specified path.",
    #     parameters={
    #         "type": "object",
    #         "properties": {
    #             "file_path": {"type": "string", "description": "The path to the file to check."}
    #         },
    #         "required": ["file_path"]
    #     },
    #     handler=file_exists
    # ))
    # registry.register(PythonTool(
    #     name="file_read",
    #     description="Read and return the contents of a file.",
    #     parameters={
    #         "type": "object",
    #         "properties": {
    #             "file_path": {"type": "string", "description": "The path to the file to read."}
    #         },
    #         "required": ["file_path"]
    #     },
    #     handler=file_read
    # ))
    # registry.register_function(fn=file_exists, )
    # registry.register_function(fn=file_read, )
    # registry.register_function(fn=file_write, )
    # registry.register_function(fn=echo, )
    # registry.register_function(fn=reverse_string, )
    # registry.register_function(fn=greet, )

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
            tools = await mcp_client.list_tools()
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
