import asyncio
import click

from geenii.tool.registry import ToolRegistry
from geenii.tools import init_builtin_tools, init_mcp_server_tools


def _init_tool_registry():
    tool_registry = ToolRegistry()
    init_builtin_tools(tool_registry)
    asyncio.run(init_mcp_server_tools(tool_registry))
    return tool_registry

@click.group()
def tools():
    """Manage and execute tools."""
    pass

@tools.command("list")
def list_tools():
    """List all registered tools."""
    click.echo("Listing tools...")
    tool_registry = _init_tool_registry()
    for tool in tool_registry.list_tools():
        click.echo(f"- {tool.name}: {tool.short_description} ({tool.type})")

@tools.command("inspect")
@click.argument("tool_name")
def inspect_tool(tool_name):
    """Show details for a specific tool."""
    click.echo(f"Showing details for tool: {tool_name}")
    try:
        tool_registry = _init_tool_registry()
        tool = tool_registry.get(tool_name)
        click.echo(f"Name: {tool.name}")
        click.echo(f"Type: {tool.type}")
        click.echo(f"Parameters: {tool.parameters}")
        click.echo(f"Description: {tool.description}")
    except KeyError:
        click.echo(f"Tool {tool_name} not found.")


@tools.command("call")
@click.argument("tool_name")
@click.option("--args", "-a", multiple=True, help="Arguments for the tool in key=value format.")
def call_tool(tool_name, **kwargs):
    """Call a tool by name with the provided arguments."""
    click.echo(f"Calling tool {tool_name} with arguments: {kwargs}")

    def parse_args(args):
        parsed = {}
        for arg in args:
            if "=" in arg:
                key, value = arg.split("=", 1)
                parsed[key] = value
            else:
                click.echo(f"Invalid argument format: {arg}. Expected key=value.")
        return parsed

    parsed_kwargs = parse_args(kwargs.get("args", []))
    del kwargs["args"]
    print("Parsed arguments:", parsed_kwargs)

    async def _run():
        # load MCP tools and invoke in the same event loop: MCP clients are cached per server
        tool_registry = ToolRegistry()
        init_builtin_tools(tool_registry)
        await init_mcp_server_tools(tool_registry)
        return await tool_registry.invoke(tool_name, args=parsed_kwargs, **kwargs)

    try:
        result = asyncio.run(_run())
        print("--- Result ---")
        print(result)
        print("--------------")
        click.echo(f"Tool {tool_name} executed successfully.")
    except Exception as e:
        click.echo(f"Error executing tool {tool_name}: {e}")
