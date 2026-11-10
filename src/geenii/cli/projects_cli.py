import os
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from geenii import config


@click.group()
def projects():
    """Manage projects."""


@projects.command(name="list")
def list_projects():
    """List the projects configured in the user settings."""
    _projects = config.get_projects()
    if not _projects:
        click.echo("No projects configured.")
        return

    # same as config.get_project_dir(), without reading the settings (and warning) twice
    cwd = Path(config.GEENII_WORKING_DIR)
    current = max(
        (p for p in _projects if cwd.is_relative_to(p)), key=len, default=None
    )
    table = Table(show_header=True)
    table.add_column("Path")
    table.add_column("Trusted")
    table.add_column("Exists")
    table.add_column("Current")
    for path, conf in _projects.items():
        table.add_row(
            path,
            "yes" if conf.get("trusted") is True else "no",
            "yes" if os.path.isdir(path) else "no",
            "*" if path == current else "",
        )
    Console().print(table)
