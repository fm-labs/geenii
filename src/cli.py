import logging
import click

from rich.logging import RichHandler

from geenii.cli.ai import ai as ai_cli
from geenii.cli.agent import agent_cli
from geenii.cli.agents import agents as agents_cli
from geenii.cli.chat_client import chat as chat_cli
from geenii.cli.info import info as info_cli
from geenii.cli.skills import skills as skills_cli
from geenii.cli.tools import tools as tools_cli
from geenii.config import APP_VERSION

logging.basicConfig(
    level="INFO",
    format="%(message)s",
    handlers=[
        RichHandler(
            show_time=True,  # show timestamps
            omit_repeated_times=False,  # show timestamp every line
            show_level=True,
            show_path=True,  # hide file path
            rich_tracebacks=False,  # beautiful exception tracebacks
        )
    ]
)
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=APP_VERSION)
def cli():
    """Geenii CLI - A versatile command-line interface for AI agents, tools, and agents."""
    pass


cli.add_command(info_cli)
cli.add_command(ai_cli)
cli.add_command(agents_cli)
cli.add_command(agent_cli)
cli.add_command(skills_cli)
cli.add_command(tools_cli)
#cli.add_command(chat_cli)


if __name__ == "__main__":
    cli()