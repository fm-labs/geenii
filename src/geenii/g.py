from geenii.utils.cached import cached
from geenii.mcp.client import McpClient, get_mcp_config
from geenii.tools import ToolRegistry

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

    from geenii.builtin.builtin_tools import geenii_tools
    for name, tool in geenii_tools._tools.items():
        registry.register(tool)

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


def execute_tool_call(registry: ToolRegistry, tool_name: str, **kwargs) -> any:
    tool = registry.get(tool_name)
    if tool is None:
        raise ValueError(f"Tool {tool_name!r} is not registered")
    print(f'$> Calling tool "{tool_name}" with args {kwargs}')
    return tool.invoke(**kwargs)
