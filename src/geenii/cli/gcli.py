import click

from geenii.cli.ai import AiCli
from geenii.cli.chat_client import ChatClientCli
from geenii.cli.info import InfoCli
from geenii.cli.skills import SkillsCli
from geenii.cli.tools import ToolsCli
from geenii.cli.agents import AgentsCli
from geenii.config import APP_VERSION


@click.group()
@click.version_option(version=APP_VERSION)
def gcli():
    """Geenii CLI - A versatile command-line interface for AI agents, tools, and agents."""
    pass

InfoCli(gcli)
AiCli(gcli)
AgentsCli(gcli)
ToolsCli(gcli)
SkillsCli(gcli)
ChatClientCli(gcli)