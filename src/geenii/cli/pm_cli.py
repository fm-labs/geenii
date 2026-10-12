import json
import shlex

import click

from geenii.daemon.client import SOCKET_ENV_VARS
from geenii.pm.process_manager_client import ProcessManagerClient


def _client(ctx) -> ProcessManagerClient:
    socket_path = ctx.obj or None
    return ProcessManagerClient(socket_path) if socket_path else ProcessManagerClient()


@click.group()
@click.option("--socket", "-s", default=None, envvar=list(SOCKET_ENV_VARS),
              help="Path to the geenii daemon's Unix socket.")
@click.pass_context
def pm(ctx, socket):
    """Manage background processes."""
    ctx.ensure_object(dict)
    ctx.obj = socket


@pm.command()
@click.pass_context
def ping(ctx):
    """Check if the geenii daemon (which hosts the process manager) is running."""
    client = _client(ctx)
    if client.is_available():
        click.echo("Process manager is running.")
    else:
        click.echo("Process manager is not reachable (is `geenii daemon start` running?).")
        raise SystemExit(1)


@pm.command()
@click.option("--socket", "-s", default=None, help="Path to the Unix socket to listen on.")
@click.pass_context
def serve(ctx, socket):
    """Alias for `geenii daemon start`: runs the daemon, which hosts the process manager."""
    from geenii.cli.daemon_cli import start_daemon
    from geenii.daemon.server import DEFAULT_SCHEDULER_CONFIG
    start_daemon(socket or ctx.obj or None, DEFAULT_SCHEDULER_CONFIG)


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
@click.option("--offset", default=None, type=int, help="Start reading at this byte position.")
@click.option("--limit", default=None, type=int, help="Read at most this many bytes.")
@click.pass_context
def output(ctx, process_id, stream, tail, offset, limit):
    """Show captured output of a background process."""
    if tail is not None and (offset is not None or limit is not None):
        raise click.UsageError("--tail cannot be combined with --offset/--limit")
    client = _client(ctx)
    text = client.output(process_id, stream=stream, tail=tail, offset=offset, limit=limit)
    click.echo(text, nl=False)


@pm.command()
@click.argument("process_id")
@click.option("--timeout", "-t", type=float, default=None, help="Give up after this many seconds.")
@click.pass_context
def wait(ctx, process_id, timeout):
    """Wait until a background process has finished and print its final state.

    Exits with the process's exit code (1 if it was killed or orphaned).
    """
    client = _client(ctx)
    try:
        result = client.wait(process_id, timeout=timeout)
    except RuntimeError as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(2 if "TimeoutError" in str(exc) else 1)
    click.echo(json.dumps(result, indent=2))
    code = result.get("exit_code")
    raise SystemExit(code if isinstance(code, int) and code >= 0 else 1)


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
        cmd = p["cmd"] if isinstance(p["cmd"], str) else shlex.join(p["cmd"])
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
