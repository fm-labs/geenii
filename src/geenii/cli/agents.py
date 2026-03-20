import click

from geenii.cli.click_helper import click_error, click_info
from geenii.g import init_agent_registry



@click.group()
def agents():
    """Manage and run agents."""
    pass


@agents.command(name="list")
def list_agents():
    """List all configured and loaded agents."""
    click.echo("Configured agents:")
    _agents = init_agent_registry(auto_load=True)
    for agent_name in _agents.list_configured():
        click.echo(f"- {agent_name}")

    click.echo("Loaded agents:")
    for agent_name in _agents.list_loaded():
        click.echo(f"- {agent_name}")


@agents.command(name="inspect")
@click.argument("name")
def inspect_agent(name: str):
    _agents = init_agent_registry(auto_load=True)
    agent_config = _agents.get_config(name)
    if not agent_config:
        click_error(f"Agent '{name}' not found. Please check the available agents with 'agents list'.")
        return
    
    click_info(f"Name: {agent_config.name}")
    click_info(f"Description: {agent_config.description}")
    click_info(f"Label: {agent_config.label}")
    click_info(f"Model: {agent_config.model}")
    click_info(f"Model Parameters: {agent_config.model_parameters}")
    click_info(f"Tools: {agent_config.tools}")
    click_info(f"Skills: {agent_config.skills}")
    click_info(f"System Prompt: {agent_config.system}")
    # print(agent_config)
