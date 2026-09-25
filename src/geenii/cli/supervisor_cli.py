import json
import os

import click
from rich.console import Console
from rich.table import Table

from geenii.cli.daemon_cli import live_daemon
from geenii.daemon.client import SOCKET_ENV_VARS, DaemonClient
from geenii.daemon.server import DEFAULT_SERVICES_CONFIG

console = Console()

CONFIG_OPTION_HELP = "Path to the services config JSON file."


def _parse_env(pairs) -> dict[str, str]:
    env = {}
    for pair in pairs:
        if "=" not in pair:
            click.echo(f"Error: invalid env format '{pair}', expected KEY=VALUE.")
            raise SystemExit(1)
        k, v = pair.split("=", 1)
        env[k] = v
    return env


def _read_file(config: str) -> dict:
    if not os.path.isfile(config):
        return {"services": []}
    with open(config) as f:
        return json.load(f)


def _write_file(config: str, data: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(config)), exist_ok=True)
    with open(config, "w") as f:
        json.dump(data, f, indent=2)


def _reload_if_live(ctx, config: str) -> None:
    client, _ = live_daemon("supervisor", config, ctx.obj or None)
    if client is None:
        return
    changes = client.call("supervisor.reload")
    summary = ", ".join(f"{k}: {', '.join(v)}" for k, v in changes.items() if v) or "no changes"
    click.echo(f"Reloaded the running daemon ({summary}).")


def _client(ctx) -> DaemonClient:
    client = DaemonClient(ctx.obj or None)
    if not client.is_available():
        click.echo(f"The geenii daemon is not running ({client.socket_path}). Start it with `geenii daemon start`.")
        raise SystemExit(1)
    return client


def _call(client: DaemonClient, method: str, params: dict | None = None):
    try:
        return client.call(method, params)
    except RuntimeError as exc:
        click.echo(f"Error: {exc}")
        raise SystemExit(1)


@click.group()
@click.option("--socket", "-s", default=None, envvar=list(SOCKET_ENV_VARS),
              help="Path to the geenii daemon's Unix socket.")
@click.pass_context
def supervisor(ctx, socket):
    """Keep long-running processes up (runs inside the geenii daemon).

    Services declared in services.json (`add`/`remove`/`list`) are started
    whenever the daemon starts. Services started with `start` are ad hoc: they
    live only as long as the daemon.
    """
    ctx.obj = socket


@supervisor.command(name="status")
@click.option("--json", "as_json", is_flag=True, help="Print the raw status as JSON.")
@click.pass_context
def status(ctx, as_json):
    """Show supervised processes and whether they are running."""
    st = _call(_client(ctx), "supervisor.status")
    if as_json:
        click.echo(json.dumps(st, indent=2))
        return
    if not st["desired"]:
        click.echo("No supervised processes.")
        return

    table = Table(title="Supervised processes")
    table.add_column("Name", style="cyan")
    table.add_column("Source", style="dim")
    table.add_column("Command", style="magenta")
    table.add_column("State")
    table.add_column("PID")
    table.add_column("Uptime", justify="right")
    table.add_column("Restart", style="dim")
    table.add_column("Last exit", style="dim")
    for name, cfg in st["desired"].items():
        rt = st["running"].get(name)
        last_exit = (rt or {}).get("last_exit")
        table.add_row(
            name,
            "file" if cfg.get("source") == "config" else "ad hoc",
            " ".join(cfg["cmd"]),
            "[bold green]running[/bold green]" if rt else "[yellow]stopped[/yellow]",
            str(rt["pid"]) if rt else "-",
            f"{rt['uptime_s']:.0f}s" if rt else "-",
            "yes" if cfg["restart"] else "no",
            f"rc={last_exit['returncode']}" if last_exit else "-",
        )
    console.print(table)


@supervisor.command(name="start")
@click.argument("name")
@click.argument("cmd", nargs=-1, required=True)
@click.option("--no-restart", is_flag=True, help="Run once; don't restart the process when it exits.")
@click.option("--env", "-e", multiple=True, help="Environment variable in KEY=VALUE format (repeatable).")
@click.option("--cwd", "-d", default=None, help="Working directory.")
@click.pass_context
def start(ctx, name, cmd, no_restart, env, cwd):
    """Start NAME running CMD and keep it running (ad hoc, until the daemon stops).

    CMD is executed directly, without a shell; use `sh -c '...'` for shell
    syntax. If NAME already exists, its configuration is replaced and takes
    effect at the next restart. Use `add` to declare a service permanently.

    \b
    Example:
      geenii supervisor start web -- python -m http.server 8000
    """
    env_dict = _parse_env(env)
    _call(_client(ctx), "supervisor.ensure", {
        "name": name, "cmd": list(cmd), "restart": not no_restart,
        "env": env_dict or None, "cwd": cwd,
    })
    click.echo(f"Supervising '{name}'.")


@supervisor.command(name="stop")
@click.argument("name")
@click.option("--keep", is_flag=True,
              help="Keep the configuration (listed as stopped) so `restart` can start it again.")
@click.pass_context
def stop(ctx, name, keep):
    """Stop NAME (and everything it started) and stop supervising it."""
    _call(_client(ctx), "supervisor.stop", {"name": name, "disable_restart": not keep})
    click.echo(f"Stopped '{name}'.")


@supervisor.command(name="restart")
@click.argument("name")
@click.pass_context
def restart(ctx, name):
    """Restart NAME now (also resets its restart backoff)."""
    _call(_client(ctx), "supervisor.restart", {"name": name})
    click.echo(f"Restarted '{name}'.")


@supervisor.command(name="logs")
@click.argument("name")
@click.option("--tail", "-n", default=100, show_default=True, help="Number of lines to show.")
@click.pass_context
def logs(ctx, name, tail):
    """Show the recent output of NAME (stdout, stderr and supervisor events)."""
    for line in _call(_client(ctx), "supervisor.logs", {"name": name, "tail": tail}):
        click.echo(line)


@supervisor.command(name="list")
@click.option("--config", "-c", default=DEFAULT_SERVICES_CONFIG, show_default=True, help=CONFIG_OPTION_HELP)
def list_services(config):
    """List the services declared in the config file (including disabled ones)."""
    services = _read_file(config).get("services", [])
    if not services:
        click.echo(f"No services configured in {config}.")
        return
    for svc in services:
        flags = " ".join(f for f in [
            "" if svc.get("enabled", True) else "(disabled)",
            "" if svc.get("restart", True) else "(no restart)",
        ] if f)
        click.echo(f"  {svc.get('name', '?'):<20} {' '.join(svc.get('cmd', []))} {flags}".rstrip())


@supervisor.command(name="add")
@click.argument("name")
@click.argument("cmd", nargs=-1, required=True)
@click.option("--no-restart", is_flag=True, help="Run once per daemon start; don't restart when it exits.")
@click.option("--env", "-e", multiple=True, help="Environment variable in KEY=VALUE format (repeatable).")
@click.option("--cwd", "-d", default=None, help="Working directory.")
@click.option("--disabled", is_flag=True, help="Add the service in disabled state.")
@click.option("--config", "-c", default=DEFAULT_SERVICES_CONFIG, show_default=True, help=CONFIG_OPTION_HELP)
@click.pass_context
def add_service(ctx, name, cmd, no_restart, env, cwd, disabled, config):
    """Declare service NAME running CMD in the config file.

    The daemon starts it whenever it starts; a running daemon that uses this
    config starts it right away.

    \b
    Example:
      geenii supervisor add web -- python -m http.server 8000
    """
    data = _read_file(config)
    if any(s.get("name") == name for s in data.get("services", [])):
        click.echo(f"Error: service '{name}' already exists in {config}.")
        raise SystemExit(1)

    entry = {"name": name, "cmd": list(cmd)}
    if no_restart:
        entry["restart"] = False
    env_dict = _parse_env(env)
    if env_dict:
        entry["env"] = env_dict
    if cwd:
        entry["cwd"] = cwd
    if disabled:
        entry["enabled"] = False
    data.setdefault("services", []).append(entry)
    _write_file(config, data)

    click.echo(f"Added service '{name}' to {config}")
    _reload_if_live(ctx, config)


@supervisor.command(name="remove")
@click.argument("name")
@click.option("--config", "-c", default=DEFAULT_SERVICES_CONFIG, show_default=True, help=CONFIG_OPTION_HELP)
@click.pass_context
def remove_service(ctx, name, config):
    """Remove service NAME from the config file (a running daemon stops it)."""
    if not os.path.isfile(config):
        click.echo(f"Config file not found: {config}")
        raise SystemExit(1)
    data = _read_file(config)
    services = data.get("services", [])
    remaining = [s for s in services if s.get("name") != name]
    if len(remaining) == len(services):
        click.echo(f"Service '{name}' not found in {config}.")
        raise SystemExit(1)
    data["services"] = remaining
    _write_file(config, data)

    click.echo(f"Removed service '{name}' from {config}")
    _reload_if_live(ctx, config)


@supervisor.command(name="reload")
@click.option("--config", "-c", default=DEFAULT_SERVICES_CONFIG, show_default=True, help=CONFIG_OPTION_HELP)
@click.pass_context
def reload_services(ctx, config):
    """Make the running daemon apply its services file (after editing it by hand).

    New services start, removed ones stop, changed ones restart, and file
    services that were stopped by hand start again. Ad-hoc services are untouched.
    """
    client, reason = live_daemon("supervisor", config, ctx.obj or None)
    if client is None:
        click.echo(f"Cannot reload: {reason}.")
        raise SystemExit(1)
    _reload_if_live(ctx, config)
