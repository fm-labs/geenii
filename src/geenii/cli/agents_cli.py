import click

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
    _agents = init_global_agent_registry()
    for agent_name in sorted(list(_agents.list_configured())):
        click.echo(f"- {agent_name}")

    #click.echo("Loaded agents:")
    #for agent_name in _agents.list_loaded():
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
        desc = f"{conf.description[:100]}..." if conf.description is not None and len(conf.description) > 100 else (conf.description or "")
        table.add_row(conf.name, desc, conf.scope, conf.class_name, conf.working_dir)
    console = Console()
    console.print(table)


@agents.command(name="inspect")
@click.option("--instructions", default=False, is_flag=True, help="Show agent instructions.")
@click.argument("name")
def inspect_agent(name: str, instructions: bool):
    _agents = init_global_agent_registry()
    agent_config = _agents.get_config(name)
    if not agent_config:
        click_error(f"Agent '{name}' not found. Please check the available agents with 'agents list'.")
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
        #click_info(f"System Instructions: {agent_config.system}")
        click_info(f"Full System Instructions: {agent_config.full_instructions}")
    # print(agent_config)
