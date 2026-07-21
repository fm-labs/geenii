import asyncio
import json

import click

from geenii.pm.process_manager_client import ProcessManagerClient
from geenii.pm.process_manager_service import ProcessManagerService


def _client(ctx) -> ProcessManagerClient:
    socket_path = ctx.obj or None
    return ProcessManagerClient(socket_path) if socket_path else ProcessManagerClient()


@click.group()
@click.option("--socket", "-s", default=None, envvar="GEENII_PM_SOCKET",
              help="Path to the process manager Unix socket.")
@click.pass_context
def pm(ctx, socket):
    """Manage background processes."""
    ctx.ensure_object(dict)
    ctx.obj = socket


@pm.command()
@click.pass_context
def ping(ctx):
    """Check if the process manager service is running."""
    client = _client(ctx)
    if client.is_available():
        click.echo("Process manager is running.")
    else:
        click.echo("Process manager is not reachable.")
        raise SystemExit(1)


@pm.command()
@click.option("--socket", "-s", default=None, help="Path to the Unix socket to listen on.")
def serve(socket):
    """Start the process manager service."""
    service = ProcessManagerService(socket) if socket else ProcessManagerService()
    click.echo(f"Starting process manager on {service.socket_path}")
    asyncio.run(service.serve_forever())


@pm.command()
@click.argument("command")
@click.option("--cwd", "-d", default=None, help="Working directory.")
@click.option("--pid", "-p", default=None, help="Custom process ID.")
@click.pass_context
def start(ctx, command, cwd, pid):
    """Start a background process."""
    client = _client(ctx)
    result = client.start(command, cwd=cwd, pid=pid)
    click.echo(json.dumps(result, indent=2))


@pm.command()
@click.argument("process_id")
@click.pass_context
def status(ctx, process_id):
    """Check the state of a background process."""
    client = _client(ctx)
    result = client.status(process_id)
    click.echo(json.dumps(result, indent=2))


@pm.command()
@click.argument("process_id")
@click.option("--stream", type=click.Choice(["stdout", "stderr"]), default="stdout")
@click.option("--tail", "-n", default=None, type=int, help="Show only the last N lines.")
@click.pass_context
def output(ctx, process_id, stream, tail):
    """Show captured output of a background process."""
    client = _client(ctx)
    text = client.output(process_id, stream=stream, tail=tail)
    click.echo(text, nl=False)


@pm.command()
@click.argument("process_id")
@click.option("--force", "-f", is_flag=True, help="Send SIGKILL instead of SIGTERM.")
@click.pass_context
def kill(ctx, process_id, force):
    """Kill a running background process."""
    client = _client(ctx)
    result = client.kill(process_id, force=force)
    click.echo(json.dumps(result, indent=2))


@pm.command(name="list")
@click.option("--all", "-a", "include_finished", is_flag=True,
              help="Include finished processes from disk.")
@click.pass_context
def list_procs(ctx, include_finished):
    """List background processes."""
    client = _client(ctx)
    procs = client.list(include_finished=include_finished)
    if not procs:
        click.echo("No processes.")
        return
    for p in procs:
        state = p["state"]
        pid = p["pid"]
        cmd = " ".join(p["cmd"])
        exit_code = p.get("exit_code")
        suffix = f" exit={exit_code}" if exit_code is not None else ""
        click.echo(f"  {pid}  {state:<10} {cmd}{suffix}")


@pm.command()
@click.argument("process_id")
@click.pass_context
def cleanup(ctx, process_id):
    """Remove on-disk logs for a finished process."""
    client = _client(ctx)
    client.cleanup(process_id)
    click.echo(f"Cleaned up {process_id}.")
