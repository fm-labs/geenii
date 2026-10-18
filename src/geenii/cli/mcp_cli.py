import hashlib
import json
import os
from pathlib import Path

import click
from mcp_types import CallToolResult

from geenii.config import CACHE_DIR
from geenii.mcp_config import get_mcp_config, get_mcp_config_for_server, get_mcp_client_for_server


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
        _type = cfg.get("type", "")
        if _type == "stdio":
            command = cfg.get("command", "")
            args = " ".join(cfg.get("args", []))
            click.echo(f"  {name:30s} {_type:10s} {command} {args}")
        elif _type == "http":
            url = cfg.get("url", "")
            click.echo(f"  {name:30s} {_type:10s} {url}")
        else:
            click.echo(f"  {name:30s} {_type:10s} Unknown")


@server.command("inspect")
@click.argument("server_id")
def server_inspect(server_id):
    """Inspect server config."""
    cfg = get_mcp_config_for_server(server_id)
    if cfg is None:
        raise click.ClickException(f"Server '{server_id}' not found.")
    click.echo(json.dumps(cfg, indent=2))


@server.command("info")
@click.argument("server_id")
def server_info(server_id):
    """List tools provided by a server."""
    client = get_mcp_client_for_server(server_id)
    try:
        info = client.info()
        if not info:
            click.echo(f"No info found for server '{server_id}'.")
            return
        click.echo(json.dumps(info, indent=2, default=str))
    except Exception as e:
        click.echo(repr(e))
        raise e
    finally:
        client.close()


@server.command("tools")
@click.argument("server_id")
def server_tools(server_id):
    """List tools provided by a server."""
    client = get_mcp_client_for_server(server_id)
    try:
        tools = client.list_tools()
        if not tools:
            click.echo(f"No tools found for server '{server_id}'.")
            return

        click.echo(json.dumps(tools, indent=2, default=str))
        # for tool in tools:
        #     name = tool.get("name", "")
        #     desc = tool.get("description", "")
        #     click.echo(f"  {name:40s} {desc}")
    except Exception as e:
        click.echo(repr(e))
        raise e
    finally:
        client.close()


@server.command("tool_info")
@click.argument("server_id")
@click.argument("tool_name")
def server_tool_info(server_id, tool_name):
    """Show tool information on a server."""
    client = get_mcp_client_for_server(server_id)
    try:
        tools = client.list_tools()
        # filter tool by name
        if tools:
            for tool in tools:
                name = tool.get("name", "")
                if name == tool_name:
                    #return tool
                    click.echo(json.dumps(tool, indent=2, default=str))
                    break
        return None
    except Exception as e:
        click.echo(repr(e))
        raise e
    finally:
        client.close()



@server.command("tool_exec")
@click.argument("server_id")
@click.argument("tool_name")
@click.option("--arg", "-a", multiple=True, help="Tool arguments in key=value format. (Multiple allowed)")
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

    client = get_mcp_client_for_server(server_id)
    try:
        result: CallToolResult = client.call_tool(tool_name, args)
        #click.echo(json.dumps(result.model_dump(), indent=2, default=str))
        if hasattr(result, "content") and len(result.content) > 0:
            content = result.content[0]
            if hasattr(content, "text"):
                click.echo(content.text)
            if hasattr(content, "structured_content"):
                click.echo(json.dumps(content.structured_content, indent=2, default=str))
        else:
            click.echo(json.dumps(result, indent=2, default=str))
    finally:
        client.close()


@server.command("resource")
@click.argument("server_id")
@click.argument("resource_name")
@click.option("--download", is_flag=True, help="Download the resource to a file.")
@click.option("--overwrite", is_flag=True, help="Overwrite existing resource.")
def server_resource(server_id: str, resource_name: str, download: bool, overwrite: bool):
    """List tools provided by a server."""
    client = get_mcp_client_for_server(server_id)
    try:
        if download:
            target_path = _resource_cache_path(server_id, resource_name)
            if os.path.exists(target_path) and not overwrite:
                click.echo(f"Resource '{resource_name}' already exists.")
                return
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            client.download_resource(resource_name, target_path, overwrite=overwrite)
            click.echo(f"Resource '{resource_name}' downloaded to '{target_path}'.")
        else:
            b_content = client.get_resource_content(resource_name)
            if not b_content:
                click.echo(f"Resource '{resource_name}' not found.")
                return
            print(b_content.decode("utf-8"))
    except Exception as e:
        click.echo(repr(e))
    finally:
        client.close()


def _resource_cache_path(server_id: str, resource_name: str) -> Path:
    # todo evaluate if resource_path should always be hashed
    if "://" in resource_name:
        resource_path = resource_name.split("://", 1)[1]
    else:
        resource_path = hashlib.md5(resource_name.encode('utf-8')).hexdigest()
    return Path(CACHE_DIR) / "mcp" / server_id / "r" / resource_path
