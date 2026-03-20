import logging

import click
from rich.logging import RichHandler

from geenii.cli.agents import agents as agents_cli
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
def geemod():
    """Geenii CLI - A versatile command-line interface for AI agents, tools, and agents."""
    pass


geemod.add_command(agents_cli)
geemod.add_command(skills_cli)
geemod.add_command(tools_cli)

if __name__ == "__main__":
    geemod()