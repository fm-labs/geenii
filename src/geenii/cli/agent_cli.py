import click
import json
import logging
import sys
import uuid

from geenii.agent.base_agent import (
    BaseAgent,
    restore_last_context_id,
    dump_last_context_id,
)
from geenii.cli.cli_runner import CliAgentRunner
from geenii.g import init_agent_by_name

logger = logging.getLogger(__name__)


@click.command(name="agent")
@click.argument("prompt", required=False)
@click.option(
    "name", "--name", "-n", default="default", help="Name of the agent to run."
)
@click.option(
    "skills",
    "--skills",
    "-s",
    default="",
    help="Comma-separated list of skills to enable for the agent.",
)
@click.option(
    "tools",
    "--tools",
    "-t",
    default="",
    help="Comma-separated list of tools to enable for the agent.",
)
@click.option(
    "model",
    "--model",
    "-m",
    default="",
    help="Override the model specified in the agent config.",
)
@click.option(
    "model_parameters",
    "--model-parameters",
    "-mp",
    default="",
    help="Override the model parameters specified in the agent config. Should be a JSON string.",
)
@click.option(
    "system_instructions",
    "--system",
    "-si",
    default="",
    help="Override the system instructions specified in the agent config.",
)
@click.option(
    "developer_instructions",
    "--developer",
    "-di",
    default="",
    help="Override the developer instructions specified in the agent config.",
)
@click.option(
    "output_format",
    "--output-format",
    "-f",
    default="text",
    help="Output format for the agent's responses. Options: text, json.",
)
@click.option(
    "context_id",
    "--context",
    "-c",
    default="",
    help="Continue a previous conversation. Creates a new conversation if omitted.",
)
@click.option(
    "interactive",
    "--interactive",
    "-i",
    is_flag=True,
    help="Continue the conversation after the initial prompt.",
)
@click.option(
    "resume",
    "--resume",
    "-r",
    is_flag=True,
    help="Resume the last conversation. Restores the memory",
)
def agent_cli(
    prompt: str,
    name: str,
    skills: str,
    tools: str,
    model: str,
    model_parameters: str,
    system_instructions: str,
    developer_instructions: str,
    output_format: str,
    context_id: str,
    interactive: bool,
    resume: bool,
):
    """
    Run an agent with the given name and initial prompt.
    Optionally override skills, tools, model, model parameters, system instructions, developer instructions, and output format.
    """
    if not sys.stdin.isatty():
        stdin_str = click.get_text_stream("stdin").read()
        if stdin_str is not None and len(stdin_str) > 0:
            click.echo("stdin: " + stdin_str)
            prompt = stdin_str

    if prompt is None or len(prompt) < 1:
        prompt = ""
        if interactive:
            prompt = click.prompt(
                text="Please enter a prompt", type=str, default="No prompt"
            )

    if context_id is None or len(context_id) < 1:
        context_id = f"{uuid.uuid4().hex}-cli"
        if resume:
            restored_context_id = restore_last_context_id(name)
            if restored_context_id is not None:
                logger.info(f"Restored context_id: {restored_context_id}")
                context_id = restored_context_id

        if interactive:
            restored_context_id = restore_last_context_id(name)
            if restored_context_id is not None:
                logger.info(f"Restored context_id: {restored_context_id}")
                click.prompt(
                    f"Want to restore last conversation? ({restored_context_id})",
                    type=click.Choice(["y", "n"]),
                    default="n",
                )

    agent_run(
        prompt=prompt,
        name=name,
        interactive=interactive,
        skills=skills,
        tools=tools,
        model=model,
        model_parameters=model_parameters,
        system_instructions=system_instructions,
        developer_instructions=developer_instructions,
        output_format=output_format,
        context_id=context_id,
    )

    dump_last_context_id(name, context_id)


def agent_run(
    prompt: str = "",
    name: str = "default",
    interactive: bool = False,
    skills: str = "",
    tools: str = "",
    model: str = "",
    model_parameters: str = "",
    system_instructions: str = "",
    developer_instructions: str = "",
    output_format: str = "text",
    context_id: str = None,
):

    click.echo(f"Running agent '{name}' with prompt: {prompt}")
    # _agents = init_agent_registry(auto_load=True)
    # gbot: BaseAgent = _agents.get_instance(name)

    # if prompt is not None:
    #     prompt = prompt.strip()
    #     if prompt.startswith("@"):
    #         prompt = prompt[1:]
    #         agent_name, prompt = prompt.split(" ", maxsplit=1)
    #         if agent_name != name:
    #             click.echo(f"Overriding agent '{name}' to '{agent_name}'")
    #             name = agent_name

    gbot: BaseAgent = init_agent_by_name(name, context_id=context_id)
    if not gbot:
        click.echo(
            f"Agent '{name}' not found. Please check the available agents with 'geenii agents list'."
        )
        return

    # Apply overrides from CLI options
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
        click.echo(f"Tool names: {tool_names}")
        gbot.allowed_tools = set(tool_names)
    if skills:
        gbot.skills.load(skills)
    if output_format:
        if output_format not in ["text", "json"]:
            click.echo(
                f"Invalid output format '{output_format}'. Supported formats are 'text' and 'json'."
            )
            return
        gbot.output_format = output_format

    logger.info(f"Agent '{name}' loaded. {repr(gbot)}")
    CliAgentRunner(gbot, interactive=interactive).run(prompt)
