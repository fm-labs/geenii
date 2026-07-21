import click
import logging

from geenii.cli.agent_cli import agent_cli, agent_run
from geenii.cli.agents_cli import agents as agents_cli
from geenii.cli.info_cli import info as info_cli
from geenii.cli.models_cli import models as models_cli
from geenii.cli.mcp_cli import mcp as mcp_cli
from geenii.cli.scheduler_cli import scheduler as scheduler_cli
from geenii.cli.skills_cli import skills as skills_cli
from geenii.cli.tools_cli import tools as tools_cli
from geenii import config
from geenii.config import APP_VERSION
from geenii.logs import init_logging

init_logging()
logger = logging.getLogger(__name__)

class FallbackGroup(click.Group):
    """Group that routes unknown commands to a default command."""

    def __init__(self, *args, fallback="handle", **kwargs):
        super().__init__(*args, **kwargs)
        self.fallback = fallback

    def resolve_command(self, ctx, args):
        try:
            return super().resolve_command(ctx, args)
        except click.UsageError:
            cmd = self.get_command(ctx, self.fallback)
            if cmd is None:
                raise
            # note: return args unchanged — do NOT strip args[0],
            # it's the input, not a command name
            print("Unknown command: {} {}".format(cmd.name, args))
            return cmd.name, cmd, args


@click.group(context_settings={"max_content_width": 130}, cls=FallbackGroup)
@click.version_option(version=APP_VERSION)
@click.option("--no-cache", is_flag=True, default=False, help="Disable caching.")
@click.option("--log-level", type=click.Choice(["DEBUG", "INFO", "WARN", "ERROR", "CRITICAL"], case_sensitive=False), default=None, help="Set the logging level.")
def geecli(no_cache, log_level):
    """Geenii CLI - A versatile command-line interface for AI agents, tools, and skills."""
    if no_cache:
        config.CACHE_DISABLED = True
    if log_level:
        logging.getLogger("geenii").setLevel(log_level.upper())
        logging.getLogger("httpx").setLevel(log_level.upper())


@geecli.command(hidden=True)  # hidden so it doesn't clutter --help
@click.option("name", "--name", "-n", default="default",
              help="Name of the agent to run.")
@click.option("skills", "--skills", "-s", default="",
              help="Comma-separated list of skills to enable for the agent.")
@click.option("tools", "--tools", "-t", default="",
              help="Comma-separated list of tools to enable for the agent.")
@click.option("model", "--model", "-m", default="",
              help="Override the model specified in the agent config.")
@click.option("model_parameters", "--model-parameters", "-mp", default="",
              help="Override the model parameters specified in the agent config. Should be a JSON string.")
@click.option("system_instructions", "--system", "-si", default="",
              help="Override the system instructions specified in the agent config.")
@click.option("developer_instructions", "--developer", "-di", default="",
              help="Override the developer instructions specified in the agent config.")
@click.option("output_format", "--output-format", "-f", default="text",
              help="Output format for the agent's responses. Options: text, json.")
@click.option("interactive", "--interactive", "-i", is_flag=True,
              help="Continue the conversation after the initial prompt.")
@click.option("conv_id", "--conv-id", "-cid", default="",
              help="Continue a previous conversation. Creates a new conversation if omitted.")
@click.argument("prompt", nargs=-1, required=True)
@click.pass_context
def handle(ctx, prompt: str, name: str, interactive: bool, skills: str, tools: str, model: str, model_parameters: str,
              system_instructions: str, developer_instructions: str, output_format: str, conv_id: str):
    print("FALLBACK HANDLE", prompt)
    if isinstance(prompt, tuple):
        prompt = prompt[0]

    agent_run(prompt=prompt, name=name, interactive=interactive, skills=skills, tools=tools,
                model=model, model_parameters=model_parameters,
                system_instructions=system_instructions, developer_instructions=developer_instructions,
                output_format=output_format, conv_id=conv_id)



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