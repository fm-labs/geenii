import logging
import click

from rich.logging import RichHandler

from geenii.cli.ai import ai
from geenii.cli.agents import agents
from geenii.cli.chat_client import chat
from geenii.cli.info import info
from geenii.cli.skills import skills
from geenii.cli.tools import tools
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


cli.add_command(info)
cli.add_command(ai)
cli.add_command(agents)
cli.add_command(skills)
cli.add_command(tools)
#gcli.add_command(chat)