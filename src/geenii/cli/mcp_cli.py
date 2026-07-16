import asyncio
import json

import click

from geenii.mcp_helper import get_mcp_config, get_mcp_config_for_server, get_mcp_client_for_server


@click.group()
def mcp():
    """Manage MCP servers and tools."""
    pass


@mcp.group("server")
def server():
    """MCP server commands."""
    pass


@server.command("list")
def server_list():
    """List servers defined in MCP config."""
    config = get_mcp_config()
    servers = config.get("mcpServers", {})
    if not servers:
        click.echo("No MCP servers configured.")
        return
    for name, cfg in servers.items():
        command = cfg.get("command", "")
        args = " ".join(cfg.get("args", []))
        click.echo(f"  {name:30s} {command} {args}")


@server.command("show")
@click.argument("server_id")
def server_show(server_id):
    """Show server config."""
    cfg = get_mcp_config_for_server(server_id)
    if cfg is None:
        raise click.ClickException(f"Server '{server_id}' not found.")
    click.echo(json.dumps(cfg, indent=2))


@server.command("tools")
@click.argument("server_id")
def server_tools(server_id):
    """List tools provided by a server."""
    async def _run():
        client = get_mcp_client_for_server(server_id)
        try:
            tools = await client.list_tools()
            if not tools:
                click.echo(f"No tools found for server '{server_id}'.")
                return
            for tool in tools:
                name = tool.get("name", "")
                desc = tool.get("description", "")
                click.echo(f"  {name:40s} {desc}")
        finally:
            await client.close()

    asyncio.run(_run())


@server.command("tool_exec")
@click.argument("server_id")
@click.argument("tool_name")
@click.option("--arg", "-a", multiple=True, help="Tool arguments in key=value format.")
@click.option("--json-args", "-j", default=None, help="Tool arguments as a JSON string.")
def server_tool_exec(server_id, tool_name, arg, json_args):
    """Execute a tool on a server."""
    if json_args:
        try:
            args = json.loads(json_args)
        except json.JSONDecodeError as e:
            raise click.ClickException(f"Invalid JSON: {e}")
    else:
        args = {}
        for a in arg:
            if "=" not in a:
                raise click.ClickException(f"Invalid argument format: '{a}'. Expected key=value.")
            key, value = a.split("=", 1)
            args[key] = value

    async def _run():
        client = get_mcp_client_for_server(server_id)
        try:
            result = await client.call_tool(tool_name, args)
            if hasattr(result, "content"):
                for item in result.content:
                    if hasattr(item, "text"):
                        click.echo(item.text)
                    else:
                        click.echo(repr(item))
            else:
                click.echo(json.dumps(result, indent=2, default=str))
        finally:
            await client.close()

    asyncio.run(_run())
