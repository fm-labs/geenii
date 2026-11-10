import asyncio
import json
import os

import click
from rich.console import Console
from rich.table import Table

from geenii.cli.daemon_cli import live_daemon
from geenii.daemon.client import DaemonClient
from geenii.daemon.server import DEFAULT_SCHEDULER_CONFIG
from geenii.pm.process_manager import ProcessManager
from geenii.scheduler import Scheduler, parse_interval

console = Console()


DEFAULT_CONFIG_PATH = DEFAULT_SCHEDULER_CONFIG


def _live_daemon(config: str) -> tuple[DaemonClient | None, str | None]:
    """(client, None) if a running daemon schedules this config file, else (None, reason)."""
    return live_daemon("scheduler", config)


def _reload_if_live(config: str) -> None:
    client, _ = _live_daemon(config)
    if client is None:
        return
    changes = client.call("scheduler.reload")
    summary = (
        ", ".join(f"{k}: {', '.join(v)}" for k, v in changes.items() if v)
        or "no changes"
    )
    click.echo(f"Reloaded the running daemon ({summary}).")


def _flags(task: dict) -> str:
    return " ".join(
        f
        for f in [
            "oneshot" if task.get("interval", "").startswith("at:") else "",
            "env" if task.get("env") else "",
            f"timeout={task['timeout']:g}s" if task.get("timeout") else "",
            "overlap" if task.get("allow_overlap") else "",
        ]
        if f
    )


@click.group()
def scheduler():
    """Manage and run the task scheduler (it runs inside the geenii daemon)."""


@scheduler.command(name="start")
@click.option(
    "--config",
    "-c",
    default=DEFAULT_CONFIG_PATH,
    help="Path to scheduler config JSON file.",
    show_default=True,
)
def start_scheduler(config):
    """Alias for `geenii daemon start --scheduler-config CONFIG`.

    The scheduler runs inside the geenii daemon, together with the process
    manager and the supervisor.
    """
    from geenii.cli.daemon_cli import start_daemon

    if not os.path.isfile(config):
        click.echo(
            f"Warning: config file not found: {config}; the scheduler starts without tasks."
        )
    start_daemon(None, config)


@scheduler.command(name="status")
@click.option(
    "--config",
    "-c",
    default=DEFAULT_CONFIG_PATH,
    help="Path to scheduler config JSON file.",
    show_default=True,
)
def status_scheduler(config):
    """Show tasks with their next/last run and whether they are running.

    Shows the live state of the running daemon. Without a daemon for this
    config, shows the tasks from the file and their next run times.
    """
    client, reason = _live_daemon(config)
    if client is not None:
        status = client.call("scheduler.status")
        if not status["tasks"]:
            click.echo("The running daemon has no scheduled tasks.")
            return
        table = Table(title=f"Scheduler Tasks — live ({config}, {status['status']})")
        table.add_column("Name", style="cyan")
        table.add_column("Interval", style="green")
        table.add_column("Command", style="magenta")
        table.add_column("Next Run", style="yellow")
        table.add_column("Last Run", style="yellow")
        table.add_column("Last Run ID", style="dim")
        table.add_column("State")
        for task in status["tasks"]:
            cmd = (
                " ".join(task["cmd"]) if task.get("cmd") else (task.get("module") or "")
            )
            table.add_row(
                task["name"],
                task["interval"],
                cmd,
                task["next_run"] or "-",
                task["last_run"] or "-",
                task.get("last_run_id") or "-",
                "[bold]running[/bold]" if task["running"] else "idle",
            )
        console.print(table)
        return

    click.echo(f"Not live: {reason}. Showing the config file.")
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
        cmd = " ".join(task.cmd) if task.cmd else task.module
        table.add_row(
            task.name,
            task.interval,
            cmd,
            task.next_run().isoformat(),
            _flags(
                {
                    "interval": task.interval,
                    "env": task.env,
                    "timeout": task.timeout,
                    "allow_overlap": task.allow_overlap,
                }
            ),
        )

    console.print(table)


@scheduler.command(name="list")
@click.option(
    "--config",
    "-c",
    default=DEFAULT_CONFIG_PATH,
    help="Path to scheduler config JSON file.",
    show_default=True,
)
def list_tasks(config):
    """List all configured tasks (from the config file, including disabled ones)."""
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
@click.option(
    "--interval",
    "-i",
    required=True,
    help="Schedule: 'cron:EXPRESSION' or 'at:DATETIME'.",
)
@click.option(
    "--env", "-e", multiple=True, help="Environment variable in KEY=VALUE format."
)
@click.option("--disabled", is_flag=True, help="Add the task in disabled state.")
@click.option(
    "--timeout",
    "-t",
    type=click.FloatRange(min=0, min_open=True),
    default=None,
    help="Kill the task if it runs longer than this many seconds.",
)
@click.option(
    "--allow-overlap",
    is_flag=True,
    help="Start a new run even if the previous run is still in progress.",
)
@click.option(
    "--config",
    default=DEFAULT_CONFIG_PATH,
    help="Path to scheduler config JSON file.",
    show_default=True,
)
def add_task(name, cmd, interval, env, disabled, timeout, allow_overlap, config):
    """Add a task to the scheduler config.

    NAME is the task identifier. CMD is the command to run (remaining arguments).
    A running daemon that uses this config picks up the change immediately.

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
    if timeout is not None:
        task_entry["timeout"] = timeout
    if allow_overlap:
        task_entry["allow_overlap"] = True
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

    os.makedirs(os.path.dirname(os.path.abspath(config)), exist_ok=True)
    with open(config, "w") as f:
        json.dump(data, f, indent=2)

    click.echo(f"Added task '{name}' to {config}")
    _reload_if_live(config)


@scheduler.command(name="remove")
@click.argument("name")
@click.option(
    "--config",
    default=DEFAULT_CONFIG_PATH,
    help="Path to scheduler config JSON file.",
    show_default=True,
)
def remove_task(name, config):
    """Remove a task from the scheduler config.

    A running daemon that uses this config picks up the change immediately;
    a run already in progress is allowed to finish.
    """
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
    _reload_if_live(config)


@scheduler.command(name="reload")
@click.option(
    "--config",
    "-c",
    default=DEFAULT_CONFIG_PATH,
    help="Path to scheduler config JSON file.",
    show_default=True,
)
def reload_config(config):
    """Make the running daemon re-read its scheduler config (after editing the file by hand)."""
    client, reason = _live_daemon(config)
    if client is None:
        click.echo(f"Cannot reload: {reason}.")
        raise SystemExit(1)
    _reload_if_live(config)


@scheduler.command(name="run")
@click.argument("name")
@click.option(
    "--config",
    "-c",
    default=DEFAULT_CONFIG_PATH,
    help="Path to scheduler config JSON file.",
    show_default=True,
)
@click.option(
    "--local",
    is_flag=True,
    help="Run in this process and wait for the result, even if the daemon is running.",
)
def run_task(name, config, local):
    """Run a single task immediately (bypassing its schedule).

    With a running daemon for this config, the run starts in the daemon and
    this command returns right away; `geenii scheduler status` shows its run
    ID, and `geenii pm output <ID>` its output. Otherwise (or with --local)
    the task runs here, the command waits and prints the output.
    """
    if not local:
        client, reason = _live_daemon(config)
        if client is not None:
            try:
                client.call("scheduler.run", {"name": name})
            except RuntimeError as exc:
                click.echo(f"Error: {exc}")
                raise SystemExit(1)
            click.echo(f"Started task '{name}' in the running daemon.")
            return
        click.echo(f"Running locally: {reason}.")

    sched = Scheduler()
    sched.load_config(config)

    task = next((t for t in sched.tasks if t.name == name), None)
    if task is None:
        click.echo(f"Task '{name}' not found in {config}")
        raise SystemExit(1)

    click.echo(f"Running task '{name}'...")

    async def run_and_collect() -> tuple[str, str] | None:
        pm = ProcessManager()
        await task.run(pm)
        if not task.last_run_id:
            return None  # a Python callable: nothing captured
        return (
            await pm.output(task.last_run_id),
            await pm.output(task.last_run_id, stream="stderr"),
        )

    captured = asyncio.run(run_and_collect())
    if captured:
        stdout, stderr = captured
        if stdout:
            click.echo(stdout, nl=False)
        if stderr:
            click.echo(stderr, nl=False, err=True)
        click.echo(f"Task '{name}' finished (process {task.last_run_id}).")
    else:
        click.echo(f"Task '{name}' finished.")
