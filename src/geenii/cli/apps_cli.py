"""
`geenii apps`: manage GeeApps through the geenii daemon.

Apps run inside the daemon as supervisor services (`app-<name>`), so they keep
running after the CLI exits. The daemon always knows the user's apps
(~/.geenii/apps); every command also sends this project's apps directory and
any `--dir`, which the daemon adds to its registry.

`init` and `init-all` only write manifest files and work without the daemon.
"""

import json
import os

import click
from rich.console import Console
from rich.table import Table

from geenii.apps import AppType, infer_manifest, read_manifest, write_manifest
from geenii.cli.click_helper import click_error, click_info, click_success, click_warning
from geenii.config import apps_dirs
from geenii.daemon.client import SOCKET_ENV_VARS, DaemonClient

console = Console()

STATUS_STYLES = {
    "running": "[bold green]running[/bold green]",
    "starting": "[yellow]starting[/yellow]",
    "error": "[red]error[/red]",
    "stopped": "[dim]stopped[/dim]",
}

dir_option = click.option(
    "--dir",
    "extra_dir",
    default=None,
    type=click.Path(exists=True, file_okay=False),
    help="Additional apps directory (added to the daemon's app registry).",
)


def _client(ctx) -> DaemonClient:
    client = DaemonClient(ctx.obj or None)
    if not client.is_available():
        click_error(f"The geenii daemon is not running ({client.socket_path}). Start it with `geenii daemon start`.")
        raise SystemExit(1)
    return client


def _app_dirs(extra_dir: str | None = None) -> list[str]:
    """App directories to send to the daemon: the known ones that exist, plus --dir"""
    dirs = [d for d in apps_dirs() if os.path.isdir(d)]
    if extra_dir:
        dirs.append(extra_dir)
    return list(dict.fromkeys(os.path.abspath(d) for d in dirs))


def _call(ctx, method: str, params: dict | None = None, extra_dir: str | None = None):
    params = {**(params or {}), "dirs": _app_dirs(extra_dir)}
    try:
        return _client(ctx).call(method, params)
    except RuntimeError as exc:
        click_error(f"Error: {exc}")
        raise SystemExit(1)


def _status(info: dict) -> str:
    return STATUS_STYLES.get(info["status"], info["status"])


def _print_started(verb: str, info: dict) -> None:
    click_success(f"{verb} '{info['name']}' (service {info['service']}, port {info['port']}).")
    click_info(f"  Logs: geenii apps logs {info['name']}")


@click.group()
@click.option(
    "--socket",
    "-s",
    default=None,
    envvar=list(SOCKET_ENV_VARS),
    help="Path to the geenii daemon's Unix socket.",
)
@click.pass_context
def apps(ctx, socket):
    """Manage GeeApps (micro applications), run by the geenii daemon."""
    ctx.obj = socket


@apps.command(name="list")
@click.option("--json", "as_json", is_flag=True, help="Print the raw app list as JSON.")
@dir_option
@click.pass_context
def list_apps(ctx, as_json, extra_dir):
    """List all apps with their runtime status."""
    app_list = _call(ctx, "apps.list", extra_dir=extra_dir)
    if as_json:
        click.echo(json.dumps(app_list, indent=2))
        return
    if not app_list:
        click_warning("No apps found.")
        return

    table = Table(title="Apps")
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Status")
    table.add_column("Port", justify="right")
    table.add_column("PID", justify="right")
    table.add_column("Title", style="dim")
    for info in app_list:
        table.add_row(
            info["name"],
            info["type"],
            _status(info),
            str(info["port"]) if info["port"] else "-",
            str(info["pid"]) if info["pid"] else "-",
            info["title"] if info["title"] != info["name"] else "",
        )
    console.print(table)


@apps.command(name="info")
@click.argument("name")
@click.option("--json", "as_json", is_flag=True, help="Print the raw app info as JSON.")
@dir_option
@click.pass_context
def info_app(ctx, name, as_json, extra_dir):
    """Show details and runtime status of an app."""
    info = _call(ctx, "apps.info", {"name": name}, extra_dir)
    if as_json:
        click.echo(json.dumps(info, indent=2))
        return
    for key, value in info.items():
        if value is None:
            continue
        if key == "status":
            console.print(f"  {key:<14} {_status(info)}")
        else:
            click.echo(f"  {key:<14} {value}")


@apps.command(name="start")
@click.argument("name")
@click.option("--port", "-p", type=int, default=None, help="Port to serve on (auto-allocated if omitted).")
@dir_option
@click.pass_context
def start_app(ctx, name, port, extra_dir):
    """Start an app as a background service of the daemon."""
    info = _call(ctx, "apps.start", {"name": name, "port": port}, extra_dir)
    _print_started("Started", info)


@apps.command(name="stop")
@click.argument("name")
@dir_option
@click.pass_context
def stop_app(ctx, name, extra_dir):
    """Stop a running app."""
    _call(ctx, "apps.stop", {"name": name}, extra_dir)
    click_success(f"Stopped '{name}'.")


@apps.command(name="restart")
@click.argument("name")
@click.option("--port", "-p", type=int, default=None, help="Port to serve on (default: the current port).")
@dir_option
@click.pass_context
def restart_app(ctx, name, port, extra_dir):
    """Restart an app, applying manifest changes (starts it if stopped)."""
    info = _call(ctx, "apps.restart", {"name": name, "port": port}, extra_dir)
    _print_started("Restarted", info)


@apps.command(name="logs")
@click.argument("name")
@click.option("--tail", "-n", type=int, default=100, show_default=True, help="Number of lines to show.")
@dir_option
@click.pass_context
def logs_app(ctx, name, tail, extra_dir):
    """Show the recent output of an app."""
    for line in _call(ctx, "apps.logs", {"name": name, "tail": tail}, extra_dir):
        click.echo(line)


@apps.command(name="reload")
@dir_option
@click.pass_context
def reload_apps(ctx, extra_dir):
    """Rescan the app directories (picks up new, removed and changed apps)."""
    result = _call(ctx, "apps.reload", extra_dir=extra_dir)
    for key in ("added", "removed"):
        if result[key]:
            click.echo(f"  {key}: {', '.join(result[key])}")
    click_success(f"Reloaded apps from {len(result['dirs'])} director{'y' if len(result['dirs']) == 1 else 'ies'}.")


def _reload_if_live(ctx, extra_dir: str | None = None) -> None:
    """Let a running daemon pick up written manifests (restart apps to apply them to running ones)"""
    client = DaemonClient(ctx.obj or None)
    if not client.is_available():
        return
    try:
        client.call("apps.reload", {"dirs": _app_dirs(extra_dir)})
    except RuntimeError as exc:
        click_warning(f"Could not reload the daemon's apps: {exc}")


def _resolve_apps_dir(name: str, extra_dir: str | None = None) -> str | None:
    """The apps directory that contains app NAME (later directories win, as in the registry)"""
    found = None
    for d in [*apps_dirs(), *([extra_dir] if extra_dir else [])]:
        if os.path.isdir(os.path.join(d, name)):
            found = d
    return found


@apps.command(name="init")
@click.argument("name")
@click.option(
    "--type",
    "-t",
    "app_type",
    type=click.Choice([t.value for t in AppType]),
    default=None,
    help="App type. Auto-detected if omitted.",
)
@click.option("--title", default=None, help="Human-readable title.")
@click.option("--description", default=None, help="Short description.")
@dir_option
@click.pass_context
def init_app(ctx, name, app_type, title, description, extra_dir):
    """Generate a manifest.json for an app directory."""
    apps_dir = _resolve_apps_dir(name, extra_dir)
    if apps_dir is None:
        click_error(f"App directory '{name}' not found in any apps path.")
        return

    app_dir = os.path.join(apps_dir, name)

    existing = read_manifest(app_dir)
    if existing is not None:
        click_warning(f"manifest.json already exists for '{name}'.")
        return

    manifest = infer_manifest(app_dir, name)
    if app_type:
        manifest.type = AppType(app_type)
    if title:
        manifest.title = title
    if description:
        manifest.description = description

    path = write_manifest(app_dir, manifest)
    click_success(f"Created {path}")
    click_info(f"  type={manifest.type.value}  main={manifest.main}")
    _reload_if_live(ctx, extra_dir)


@apps.command(name="init-all")
@click.option("--overwrite", is_flag=True, default=False, help="Overwrite existing manifests.")
@click.option(
    "--dir",
    "apps_dir",
    default=None,
    type=click.Path(exists=True, file_okay=False),
    help="Apps directory to scan. Defaults to all known apps paths.",
)
@click.pass_context
def init_all_apps(ctx, overwrite, apps_dir):
    """Generate manifest.json for all apps that lack one."""
    dirs = [apps_dir] if apps_dir else [d for d in apps_dirs() if os.path.isdir(d)]
    if not dirs:
        click_error("No apps directories found.")
        return

    created = 0
    skipped = 0
    for scan_dir in dirs:
        for entry in sorted(os.listdir(scan_dir)):
            entry_path = os.path.join(scan_dir, entry)
            if not os.path.isdir(entry_path) or entry.startswith("."):
                continue

            existing = read_manifest(entry_path)
            if existing is not None and not overwrite:
                skipped += 1
                continue

            manifest = infer_manifest(entry_path, entry)
            write_manifest(entry_path, manifest)
            click.echo(f"  {entry:<24} -> {manifest.type.value} (main={manifest.main})")
            created += 1

    click_success(f"\nCreated {created} manifest(s), skipped {skipped}.")
    if created:
        _reload_if_live(ctx, apps_dir)
