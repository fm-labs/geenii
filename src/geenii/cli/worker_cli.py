"""geenii worker: run unattended agent instances, and use agent mail and the blackboard as the human.

    geenii worker serve <agent> [--model M] [--approve none|all|a,b] [--poll S] [--once]
    geenii worker ask <agent> <text ...> [--from NAME] [--timeout S]
    geenii worker list
    geenii worker inbox [<agent>] [--read ID] [--all]
    geenii worker send <to> <subject> <body> [--from NAME]
    geenii worker blackboard [--topic T] [--limit N]
    geenii worker post <topic> <text> [--as NAME]

To list agents use `geenii agents list`; to chat with one use `geenii agent`.
"""

import functools
from datetime import UTC, datetime

import click
from rich.console import Console
from rich.table import Table

console = Console()


def _value_errors_as_click(fn):
    """Show a ValueError (unknown agent, bad message id, empty text, ...) as a clean CLI error."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError as e:
            raise click.ClickException(str(e)) from e

    return wrapper


def _require_agent(name: str):
    from geenii.g import get_agent_registry

    spec = get_agent_registry().get_config(name)
    if spec is None:
        raise click.ClickException(f"Unknown agent '{name}'. Run 'geenii agents list' to see all agents.")
    return spec


def _ago(ts: str | None) -> int | None:
    try:
        return int((datetime.now(UTC) - datetime.fromisoformat(ts)).total_seconds())
    except (TypeError, ValueError):
        return None


def _duration(seconds: int | None) -> str:
    if seconds is None:
        return ""
    return f"{seconds // 60}m{seconds % 60:02d}s" if seconds >= 60 else f"{seconds}s"


@click.group()
def worker():
    """Run unattended agent instances and use agent mail and the blackboard."""


@worker.command(name="serve")
@click.argument("agent")
@click.option("--model", "-m", default=None, help="Model id, e.g. ollama:qwen3:8b (default: the agent's model).")
@click.option(
    "--approve",
    envvar="GEENII_APPROVE",
    default="none",
    show_default=True,
    help="Tool calls to approve: 'none', 'all', or a comma-separated list of tool names. Env: GEENII_APPROVE.",
)
@click.option("--poll", default=2.0, show_default=True, type=float, help="Seconds between inbox checks.")
@click.option("--once", is_flag=True, default=False, help="Stop when the inbox is empty.")
@_value_errors_as_click
def serve_worker(agent, model, approve, poll, once):
    """Run an unattended instance that answers the mail of AGENT.

    Several instances of the same agent can run at once; each message is handled by one of them.
    Stop with Ctrl-C or SIGTERM; the current message is finished first.
    """
    from geenii.worker import serve

    serve(_require_agent(agent), model=model, poll_seconds=poll, once=once, approval_policy=approve)


@worker.command(name="ask")
@click.argument("agent")
@click.argument("text", nargs=-1, required=True)
@click.option("--from", "sender", default="human", show_default=True, help="Sender name.")
@click.option("--timeout", default=300.0, show_default=True, type=float, help="Seconds to wait for the reply.")
@_value_errors_as_click
def ask_worker(agent, text, sender, timeout):
    """Mail TEXT to a running AGENT and print its reply."""
    from geenii.worker import ask

    _require_agent(agent)
    reply = ask(agent, " ".join(text), sender=sender, timeout=timeout)
    if reply is None:
        raise click.ClickException(
            f"No reply within {timeout:g}s. Is 'geenii worker serve {agent}' running?"
        )
    click.echo(reply["body"])


@worker.command(name="list")
def list_workers():
    """List running worker instances."""
    from geenii.worker import list_workers as _list_workers

    workers = _list_workers()
    if not workers:
        click.echo("No workers running.")
        return
    table = Table(title="Workers")
    table.add_column("Agent", style="cyan")
    table.add_column("Instance", style="dim")
    table.add_column("Status", style="green")
    table.add_column("Handled", justify="right")
    table.add_column("Started", style="yellow")
    for w in workers:
        if not w["alive"]:
            status = f"[red]gone?[/red] (last seen {_duration(w['seconds_since_seen'])} ago)"
        elif w.get("status") == "busy":
            status = f"busy {_duration(_ago(w.get('busy_since')))}".strip()
        else:
            status = w.get("status", "?")
        table.add_row(w.get("agent", "?"), w.get("instance", "?"), status, str(w.get("handled", 0)),
                      w.get("started", ""))
    console.print(table)


@worker.command(name="inbox")
@click.argument("agent", default="human")
@click.option("--read", "message_id", default=None, metavar="ID", help="Show one message and mark it read.")
@click.option("--all", "include_read", is_flag=True, default=False, help="Include read messages.")
@_value_errors_as_click
def inbox(agent, message_id, include_read):
    """Show the inbox of AGENT (default: your own, 'human')."""
    from geenii.ibc.comms import Mailbox, format_inbox

    mailbox = Mailbox(agent)
    if not message_id:
        click.echo(format_inbox(mailbox.list(include_read=include_read)))
        return
    message = mailbox.read(message_id)
    click.echo(f"From: {message['from']}\nTo: {message['to']}\nDate: {message['ts']}\nSubject: {message['subject']}")
    if message.get("reply_to"):
        click.echo(f"In reply to: {message['reply_to']}")
    click.echo(f"\n{message['body']}")


@worker.command(name="send")
@click.argument("to")
@click.argument("subject")
@click.argument("body")
@click.option("--from", "sender", default="human", show_default=True, help="Sender name.")
@_value_errors_as_click
def send(to, subject, body, sender):
    """Send agent mail to TO (an agent name or 'human')."""
    from geenii.ibc.comms import Mailbox, known_agents

    if to not in known_agents():
        raise click.ClickException(f"Unknown agent '{to}'. Run 'geenii agents list' to see all agents.")
    message = Mailbox.send(sender, to, subject, body)
    click.echo(f"Sent {message['id']} to {to}.")


@worker.command(name="blackboard")
@click.option("--topic", "-t", default=None, help="Only entries with this topic.")
@click.option("--limit", "-n", default=20, show_default=True, type=int, help="Maximum number of entries.")
def blackboard(topic, limit):
    """Read the shared blackboard."""
    from geenii.ibc.comms import Blackboard, format_blackboard

    board = Blackboard()
    click.echo(format_blackboard(board.read(topic=topic, limit=limit)))
    topics = board.topics() if not topic else {}
    if topics:
        click.echo("\nTopics: " + ", ".join(f"{t} ({n})" for t, n in topics.items()))


@worker.command(name="post")
@click.argument("topic")
@click.argument("text")
@click.option("--as", "author", default="human", show_default=True, help="Author name.")
@_value_errors_as_click
def post(topic, text, author):
    """Post TEXT under TOPIC to the shared blackboard."""
    from geenii.ibc.comms import Blackboard

    entry = Blackboard().post(author, topic, text)
    click.echo(f"Posted {entry['id']} on {entry['topic']}.")
