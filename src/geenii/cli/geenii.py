import json
import logging

import click

from geenii.agent.base_agent import BaseAgent
from geenii.cli.cli_runner import CliAgentRunner
from geenii.g import init_agent_registry

logger = logging.getLogger(__name__)


@click.command(name="agent")
@click.argument("prompt")
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
@click.option("continue_conversation", "--continue", "-c", is_flag=True,
              help="Continue the conversation after the initial prompt.")
def agent_cli(prompt: str, name: str, continue_conversation: bool, skills: str, tools: str, model: str, model_parameters: str,
              system_instructions: str, developer_instructions: str, output_format: str):
    """
    Run an agent with the given name and initial prompt.
    Optionally override skills, tools, model, model parameters, system instructions, developer instructions, and output format.
    """
    click.echo(f"Running agent '{name}' with prompt: {prompt}")
    _agents = init_agent_registry(auto_load=True)
    gbot: BaseAgent = _agents.get_instance(name)
    if not gbot:
        click.echo(f"Agent '{name}' not found. Please check the available agents with 'geemod agents list'.")
        return

    # todo Apply overrides from CLI options
    if model:
        gbot.model = model
    if model_parameters:
        try:
            gbot.model_parameters = json.loads(model_parameters)
        except json.JSONDecodeError as e:
            click.echo(f"Invalid JSON for model parameters: {e}")
            return
    if system_instructions:
        gbot.system_prompt = system_instructions
    if developer_instructions:
        gbot.developer_prompt = developer_instructions
    if tools:
        tool_names = [tool.strip() for tool in tools.split(",")]
        gbot.allowed_tools = set(tool_names)
    if skills:
        gbot.skills.load(skills)
    if output_format:
        if output_format not in ["text", "json"]:
            click.echo(f"Invalid output format '{output_format}'. Supported formats are 'text' and 'json'.")
            return
        gbot.output_format = output_format

    CliAgentRunner(gbot, interactive=continue_conversation).run(prompt)