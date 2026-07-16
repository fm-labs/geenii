import click
import logging

from geenii.cli.agent_cli import agent_cli
from geenii.cli.agents_cli import agents as agents_cli
from geenii.cli.info_cli import info as info_cli
from geenii.cli.models_cli import models as models_cli
from geenii.cli.mcp_cli import mcp as mcp_cli
from geenii.cli.scheduler_cli import scheduler as scheduler_cli
from geenii.cli.skills_cli import skills as skills_cli
from geenii.cli.tools_cli import tools as tools_cli
from geenii.config import APP_VERSION
from geenii.logs import init_logging

init_logging()
logger = logging.getLogger(__name__)


@click.group(context_settings={"max_content_width": 130})
@click.version_option(version=APP_VERSION)
def geecli():
    """Geenii CLI - A versatile command-line interface for AI agents, tools, and skills."""
    pass


geecli.add_command(info_cli)
geecli.add_command(agent_cli)
geecli.add_command(agents_cli)
geecli.add_command(models_cli)
geecli.add_command(mcp_cli)
geecli.add_command(tools_cli)
geecli.add_command(skills_cli)
geecli.add_command(scheduler_cli)


def main():
    #init_app_directories()
    geecli()


if __name__ == "__main__":
    main()