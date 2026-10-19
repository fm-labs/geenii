import json
import os

import click

from geenii.daemon.client import SOCKET_ENV_VARS, DaemonClient

SOCKET_OPTION_HELP = "Path to the daemon's Unix socket."


def _client(socket) -> DaemonClient:
    return DaemonClient(socket)


def live_daemon(component: str, config: str, socket: str | None = None) -> tuple[DaemonClient | None, str | None]:
    """Return (client, None) if a running daemon uses `config` for `component` ("scheduler"/"supervisor").

    Otherwise (None, reason): the daemon isn't running, or it uses another config file.
    """
    client = _client(socket)
    if not client.is_available():
        return None, "the geenii daemon is not running"
    daemon_config = client.info()[component].get("config")
    if daemon_config != os.path.abspath(config):
        return None, f"the running daemon uses a different config ({daemon_config})"
    return client, None


def start_daemon(socket: str | None, scheduler_config: str | None, services_config: str | None = None) -> None:
    """Run the daemon in the foreground (shared by `daemon start` and its aliases)."""
    from geenii.daemon.server import DEFAULT_SERVICES_CONFIG, DaemonAlreadyRunning, run_daemon

    client = _client(socket)
    click.echo(f"Starting geenii daemon on {client.socket_path}")
    try:
        run_daemon(client.socket_path, scheduler_config, services_config or DEFAULT_SERVICES_CONFIG)
    except DaemonAlreadyRunning as exc:
        click.echo(f"Error: {exc}", err=True)
        raise SystemExit(1)


@click.group()
def daemon():
    """Run and control the geenii daemon (process manager, scheduler, supervisor)."""
    pass


@daemon.command(name="start")
@click.option("--socket", "-s", default=None, envvar=list(SOCKET_ENV_VARS), help=SOCKET_OPTION_HELP)
@click.option("--scheduler-config", "-c", default=None,
              help="Scheduler config JSON. Default: $GEENII_WORKING_DIR/.geenii/scheduler.json (if it exists).")
@click.option("--services-config", default=None,
              help="Supervised services JSON. Default: $GEENII_WORKING_DIR/.geenii/services.json (if it exists).")
def start(socket, scheduler_config, services_config):
    """Run the daemon in the foreground until SIGINT/SIGTERM."""
    from geenii.daemon.server import DEFAULT_SCHEDULER_CONFIG
    start_daemon(socket, scheduler_config or DEFAULT_SCHEDULER_CONFIG, services_config)


@daemon.command(name="status")
@click.option("--socket", "-s", default=None, envvar=list(SOCKET_ENV_VARS), help=SOCKET_OPTION_HELP)
def status(socket):
    """Show whether the daemon is running and what it hosts."""
    client = _client(socket)
    if not client.is_available():
        click.echo(f"The geenii daemon is not running ({client.socket_path}).")
        raise SystemExit(1)
    click.echo(json.dumps(client.info(), indent=2))


@daemon.command(name="stop")
@click.option("--socket", "-s", default=None, envvar=list(SOCKET_ENV_VARS), help=SOCKET_OPTION_HELP)
def stop(socket):
    """Ask the running daemon to shut down (terminates the processes it manages)."""
    client = _client(socket)
    if not client.is_available():
        click.echo(f"The geenii daemon is not running ({client.socket_path}).")
        raise SystemExit(1)
    client.shutdown()
    click.echo("Daemon is shutting down.")
