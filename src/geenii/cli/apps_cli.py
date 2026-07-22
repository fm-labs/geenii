import sys

import signal

import time

import os

import click

from geenii.apps import AppRegistry, read_manifest, write_manifest, infer_manifest
from geenii.cli.click_helper import click_success, click_error, click_info, click_warning
from geenii.config import GEENII_DIR, GEENII_WORKING_DIR
from geenii.utils.os_util import get_user_home_dir


def _apps_dirs() -> list[str]:
    return [
        os.path.join(get_user_home_dir(), ".geenii", "apps"),
        os.path.join(GEENII_WORKING_DIR, ".geenii", "apps"),
        os.path.join(GEENII_DIR, "apps"),
    ]


def _load_registry(extra_dir: str | None = None) -> AppRegistry:
    registry = AppRegistry()
    dirs = _apps_dirs()
    if extra_dir:
        dirs.append(extra_dir)
    for d in dirs:
        if os.path.isdir(d):
            registry.load_from_directory(d)
    return registry


def _resolve_apps_dir(name: str) -> str | None:
    for d in _apps_dirs():
        candidate = os.path.join(d, name)
        if os.path.isdir(candidate):
            return d
    return None


@click.group()
def apps():
    """Manage GeeApps (micro applications)."""
    pass


@apps.command(name="list")
@click.option("--status", "-s", is_flag=True, help="Show runtime status for each app.")
@click.option("--dir", "extra_dir", default=None, type=click.Path(exists=True), help="Additional apps directory.")
def list_apps(status, extra_dir):
    """List all registered apps."""
    registry = _load_registry(extra_dir)
    app_list = registry.list()
    if not app_list:
        click_warning("No apps found.")
        return

    for app in app_list:
        label = f"  {app.name:<24} {app.manifest.type.value:<8}"
        if app.manifest.title:
            label += f"  {app.manifest.title}"
        if status:
            label += f"  [{app.status.value}]"
        click.echo(label)

    click_info(f"\n  {len(app_list)} app(s)")


@apps.command(name="info")
@click.argument("name")
@click.option("--dir", "extra_dir", default=None, type=click.Path(exists=True), help="Additional apps directory.")
def info_app(name, extra_dir):
    """Show details for a specific app."""
    registry = _load_registry(extra_dir)
    app = registry.get(name)
    if app is None:
        click_error(f"App '{name}' not found.")
        return

    info = app.info()
    for key, value in info.items():
        if value is not None:
            click.echo(f"  {key:<14} {value}")


@apps.command(name="start")
@click.argument("name")
@click.option("--port", "-p", type=int, default=None, help="Port to serve on.")
@click.option("--dir", "extra_dir", default=None, type=click.Path(exists=True), help="Additional apps directory.")
def start_app(name, port, extra_dir):
    """Start an app."""
    registry = _load_registry(extra_dir)
    try:
        app = registry.start_app(name, port=port)
    except KeyError:
        click_error(f"App '{name}' not found.")
        return
    except RuntimeError as e:
        click_error(str(e))
        return

    # register signal handler
    def signal_handler(signal, frame):
        print("Received Ctrl+C", signal, file=sys.stderr)
        app.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGHUP, signal_handler)

    click_success(f"Started '{name}' (pid={app.pid}, port={app.port})")
    click_info("Press Ctrl+C to exit.")
    while True:
        time.sleep(1)


@apps.command(name="stop")
@click.argument("name")
@click.option("--dir", "extra_dir", default=None, type=click.Path(exists=True), help="Additional apps directory.")
def stop_app(name, extra_dir):
    """Stop a running app."""
    registry = _load_registry(extra_dir)
    try:
        stopped = registry.stop_app(name)
    except KeyError:
        click_error(f"App '{name}' not found.")
        return

    if stopped:
        click_success(f"Stopped '{name}'.")
    else:
        click_warning(f"App '{name}' was not running.")


@apps.command(name="init")
@click.argument("name")
@click.option("--type", "-t", "app_type", type=click.Choice(["webapp", "node", "binary"]), default=None,
              help="App type. Auto-detected if omitted.")
@click.option("--title", default=None, help="Human-readable title.")
@click.option("--description", default=None, help="Short description.")
@click.option("--dir", "extra_dir", default=None, type=click.Path(exists=True), help="Additional apps directory.")
def init_app(name, app_type, title, description, extra_dir):
    """Generate a manifest.json for an app directory."""
    apps_dir = _resolve_apps_dir(name)
    if apps_dir is None and extra_dir:
        candidate = os.path.join(extra_dir, name)
        if os.path.isdir(candidate):
            apps_dir = extra_dir
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
        from geenii.apps import AppType
        manifest.type = AppType(app_type)
    if title:
        manifest.title = title
    if description:
        manifest.description = description

    path = write_manifest(app_dir, manifest)
    click_success(f"Created {path}")
    click_info(f"  type={manifest.type.value}  main={manifest.main}")


@apps.command(name="init-all")
@click.option("--overwrite", is_flag=True, default=False, help="Overwrite existing manifests.")
@click.option("--dir", "apps_dir", default=None, type=click.Path(exists=True),
              help="Apps directory to scan. Defaults to all known apps paths.")
def init_all_apps(overwrite, apps_dir):
    """Generate manifest.json for all apps that lack one."""
    dirs = [apps_dir] if apps_dir else [d for d in _apps_dirs() if os.path.isdir(d)]
    if not dirs:
        click_error("No apps directories found.")
        return

    created = 0
    skipped = 0
    for scan_dir in dirs:
        for entry in sorted(os.listdir(scan_dir)):
            entry_path = os.path.join(scan_dir, entry)
            if not os.path.isdir(entry_path):
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
