import click

from geenii.agent.env import AgentEnvStore
from geenii.cli.click_helper import click_error, click_info
from geenii.g import init_global_agent_registry

from rich.table import Table
from rich.console import Console


@click.group()
def agents():
    """Manage and run agents."""
    pass


@agents.command(name="list")
def list_agents():
    """List all configured and loaded agents."""
    click.echo("Configured agents:")
    _agents = init_global_agent_registry(projects=True)
    for agent_name in sorted(list(_agents.list_configured())):
        click.echo(f"- {agent_name}")

    # click.echo("Loaded agents:")
    # for agent_name in _agents.list_loaded():
    #    click.echo(f"- {agent_name}")

    table = Table(show_header=True)
    table.add_column("Name")
    table.add_column("Description")
    table.add_column("Scope")
    table.add_column("Class Name")
    table.add_column("Working Directory")

    for agent_name in sorted(list(_agents.list_configured())):
        conf = _agents.get_config(agent_name)
        if not conf:
            continue
        desc = (
            f"{conf.description[:60]}..."
            if conf.description is not None and len(conf.description) > 60
            else (conf.description or "")
        )
        table.add_row(conf.name, desc, conf.scope, conf.class_name, conf.working_dir)
    console = Console()
    console.print(table)


@agents.command(name="inspect")
@click.option(
    "--instructions", default=False, is_flag=True, help="Show agent instructions."
)
@click.argument("name")
def inspect_agent(name: str, instructions: bool):
    _agents = init_global_agent_registry()
    agent_config = _agents.get_config(name)
    if not agent_config:
        click_error(
            f"Agent '{name}' not found. Please check the available agents with 'agents list'."
        )
        return

    if not instructions:
        click_info(f"Name: {agent_config.name}")
        click_info(f"Description: {agent_config.description}")
        click_info(f"Label: {agent_config.label}")
        click_info(f"Model: {agent_config.model}")
        click_info(f"Model Parameters: {agent_config.model_parameters}")
        click_info(f"Tools: {agent_config.tools}")
        click_info(f"Skills: {agent_config.skills}")
        click_info(f"Scope: {agent_config.scope}")
        click_info(f"Working Directory: {agent_config.working_dir}")
        click_info(f"Allowed Directories: {agent_config.allowed_dirs}")
        click_info("Instructions: Use the --instructions flag")
    else:
        # click_info(f"System Instructions: {agent_config.system}")
        click_info(f"Full System Instructions: {agent_config.full_instructions}")
    # print(agent_config)


@agents.group(name="env")
def agent_env():
    """Manage an agent's environment variables and secrets."""
    pass


@agent_env.command(name="list")
@click.argument("name")
def list_agent_env(name: str):
    """List the agent's variables, and the names of its secrets."""
    store = AgentEnvStore()
    table = Table(show_header=True)
    table.add_column("Name")
    table.add_column("Value")
    table.add_column("Type")
    for key, value in store.get_vars(name).items():
        table.add_row(key, value, "var")
    for key in store.secret_keys(name):
        table.add_row(key, "********", "secret")
    Console().print(table)


@agent_env.command(name="set")
@click.argument("name")
@click.argument("assignment")
@click.option(
    "--secret",
    is_flag=True,
    default=False,
    help="Store as a secret. The value is prompted for when omitted.",
)
def set_agent_env(name: str, assignment: str, secret: bool):
    """Set a variable or secret: KEY=VALUE, or just KEY with --secret to be prompted for the value."""
    key, sep, value = assignment.partition("=")
    if not sep:
        if not secret:
            click_error("Use KEY=VALUE, or --secret to be prompted for the value.")
            return
        value = click.prompt(f"Value of {key}", hide_input=True)
    store = AgentEnvStore()
    try:
        if secret:
            store.set_secret(name, key, value)
        else:
            store.set_var(name, key, value)
    except ValueError as e:
        click_error(str(e))
        return
    click_info(f"{'Secret' if secret else 'Variable'} {key} set for agent '{name}'.")


@agent_env.command(name="unset")
@click.argument("name")
@click.argument("key")
@click.option(
    "--secret",
    is_flag=True,
    default=False,
    help="Remove a secret instead of a variable.",
)
def unset_agent_env(name: str, key: str, secret: bool):
    """Remove a variable or secret."""
    store = AgentEnvStore()
    removed = store.delete_secret(name, key) if secret else store.delete_var(name, key)
    if not removed:
        click_error(
            f"{'Secret' if secret else 'Variable'} {key} not found for agent '{name}'."
        )
        return
    click_info(
        f"{'Secret' if secret else 'Variable'} {key} removed from agent '{name}'."
    )
