import asyncio
import json
import os
import sys

import click
from rich.console import Console
from rich.table import Table

from geenii.config import GEENII_DIR
from geenii.scheduler import Scheduler, parse_interval, main as scheduler_main

console = Console()


DEFAULT_CONFIG_PATH = f"{GEENII_DIR}/scheduler.json"


@click.group()
def scheduler():
    """Manage and run the task scheduler."""
    pass


@scheduler.command(name="start")
@click.option("--config", "-c", default=DEFAULT_CONFIG_PATH,
              help="Path to scheduler config JSON file.", show_default=True)
def start_scheduler(config):
    """Start the scheduler and run tasks on their schedules."""
    sched = Scheduler()
    sched.load_config(config)

    if not sched.tasks:
        click.echo("No tasks loaded. Check your config file.")
        raise SystemExit(1)

    click.echo(f"Starting scheduler with {len(sched.tasks)} task(s) from {config}")

    sys.argv = [sys.argv[0], config]
    scheduler_main()


@scheduler.command(name="status")
@click.option("--config", "-c", default=DEFAULT_CONFIG_PATH,
              help="Path to scheduler config JSON file.", show_default=True)
def status_scheduler(config):
    """Show loaded tasks and their next run times."""
    sched = Scheduler()
    sched.load_config(config)

    if not sched.tasks:
        click.echo("No tasks loaded.")
        return

    table = Table(title=f"Scheduler Tasks ({config})")
    table.add_column("Name", style="cyan")
    table.add_column("Interval", style="green")
    table.add_column("Command", style="magenta")
    table.add_column("Next Run", style="yellow")
    table.add_column("Flags", style="dim")

    for task in sched.tasks:
        next_run = task.next_run()
        cmd = " ".join(task.cmd) if task.cmd else task.module
        flags = " ".join(f for f in [
            "oneshot" if task.is_oneshot else "",
            "env" if task.env else "",
        ] if f)
        table.add_row(task.name, task.interval, cmd, next_run.isoformat(), flags)

    console.print(table)


@scheduler.command(name="list")
@click.option("--config", "-c", default=DEFAULT_CONFIG_PATH,
              help="Path to scheduler config JSON file.", show_default=True)
def list_tasks(config):
    """List all configured tasks."""
    if not os.path.isfile(config):
        click.echo(f"Config file not found: {config}")
        raise SystemExit(1)

    with open(config) as f:
        data = json.load(f)

    tasks = data.get("tasks", [])
    if not tasks:
        click.echo("No tasks configured.")
        return

    for t in tasks:
        name = t.get("name", "?")
        interval = t.get("interval", "?")
        cmd = " ".join(t["cmd"]) if t.get("cmd") else ""
        enabled = t.get("enabled", True)
        flag = "" if enabled else " (disabled)"
        click.echo(f"  {name:<20} {interval:<25} {cmd}{flag}")


@scheduler.command(name="add")
@click.argument("name")
@click.argument("cmd", nargs=-1, required=True)
@click.option("--interval", "-i", required=True,
              help="Schedule: 'cron:EXPRESSION' or 'at:DATETIME'.")
@click.option("--env", "-e", multiple=True, help="Environment variable in KEY=VALUE format.")
@click.option("--disabled", is_flag=True, help="Add the task in disabled state.")
@click.option("--config", default=DEFAULT_CONFIG_PATH,
              help="Path to scheduler config JSON file.", show_default=True)
def add_task(name, cmd, interval, env, disabled, config):
    """Add a task to the scheduler config.

    NAME is the task identifier. CMD is the command to run (remaining arguments).

    \b
    Examples:
      geenii scheduler add cleanup echo cleanup --interval 'cron:0 * * * *'
      geenii scheduler add oneshot echo done --interval 'at:2026-07-21T18:00:00Z'
    """
    try:
        parse_interval(interval)
    except ValueError as exc:
        click.echo(f"Error: {exc}")
        raise SystemExit(1)

    data = {"tasks": []}
    if os.path.isfile(config):
        with open(config) as f:
            data = json.load(f)

    for t in data.get("tasks", []):
        if t.get("name") == name:
            click.echo(f"Error: task '{name}' already exists.")
            raise SystemExit(1)

    task_entry = {
        "enabled": not disabled,
        "name": name,
        "interval": interval,
        "cmd": list(cmd),
    }
    if env:
        env_dict = {}
        for pair in env:
            if "=" not in pair:
                click.echo(f"Error: invalid env format '{pair}', expected KEY=VALUE.")
                raise SystemExit(1)
            k, v = pair.split("=", 1)
            env_dict[k] = v
        task_entry["env"] = env_dict

    data.setdefault("tasks", []).append(task_entry)

    os.makedirs(os.path.dirname(config), exist_ok=True)
    with open(config, "w") as f:
        json.dump(data, f, indent=2)

    click.echo(f"Added task '{name}' to {config}")


@scheduler.command(name="remove")
@click.argument("name")
@click.option("--config", default=DEFAULT_CONFIG_PATH,
              help="Path to scheduler config JSON file.", show_default=True)
def remove_task(name, config):
    """Remove a task from the scheduler config."""
    if not os.path.isfile(config):
        click.echo(f"Config file not found: {config}")
        raise SystemExit(1)

    with open(config) as f:
        data = json.load(f)

    tasks = data.get("tasks", [])
    original_len = len(tasks)
    data["tasks"] = [t for t in tasks if t.get("name") != name]

    if len(data["tasks"]) == original_len:
        click.echo(f"Task '{name}' not found.")
        raise SystemExit(1)

    with open(config, "w") as f:
        json.dump(data, f, indent=2)

    click.echo(f"Removed task '{name}' from {config}")


@scheduler.command(name="run")
@click.argument("name")
@click.option("--config", "-c", default=DEFAULT_CONFIG_PATH,
              help="Path to scheduler config JSON file.", show_default=True)
def run_task(name, config):
    """Run a single task immediately (bypassing its schedule)."""
    sched = Scheduler()
    sched.load_config(config)

    task = next((t for t in sched.tasks if t.name == name), None)
    if task is None:
        click.echo(f"Task '{name}' not found in {config}")
        raise SystemExit(1)

    click.echo(f"Running task '{name}'...")
    asyncio.run(task.run())
    click.echo(f"Task '{name}' finished.")
