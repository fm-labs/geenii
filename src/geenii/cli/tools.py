import click

from geenii.cli.base import BaseCli
from geenii.rt import init_builtin_tools
from geenii.tools import ToolRegistry


class ToolsCli(BaseCli):

    def __init__(self, cli: click.core.Group):
        super().__init__(cli)
        self.tool_registry = ToolRegistry()
        init_builtin_tools(self.tool_registry)

        @cli.group()
        def tools():
            """Manage and execute tools."""
            pass

        @tools.command("list")
        def list_tools():
            """List all registered tools."""
            click.echo("Listing tools...")
            tool_registry = self.tool_registry
            for tool in tool_registry.list_tools():
                click.echo(f"- {tool.name}: {tool.description} ({tool.type})")

        @tools.command("inspect")
        @click.argument("tool_name")
        def inspect_tool(tool_name):
            """Show details for a specific tool."""
            click.echo(f"Showing details for tool: {tool_name}")
            tool_registry = self.tool_registry
            try:
                tool = tool_registry.get(tool_name)
                click.echo(f"Name: {tool.name}")
                click.echo(f"Type: {tool.type}")
                click.echo(f"Description: {tool.description}")
                click.echo(f"Parameters: {tool.parameters}")
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

            kwargs = parse_args(kwargs.get("args", []))

            try:
                tool_registry = self.tool_registry
                result = tool_registry.invoke(tool_name, **kwargs)
                print("--- Result ---")
                print(result)
                print("--------------")
                click.echo(f"Tool {tool_name} executed successfully.")
            except Exception as e:
                click.echo(f"Error executing tool {tool_name}: {e}")
