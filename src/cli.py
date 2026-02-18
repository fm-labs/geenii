from typing import List

import click

from geenii.ai import generate_completion, generate_chat_completion
from geenii.datamodels import ModelMessage
from geenii.g import get_tool_registry
from geenii.config import DEFAULT_COMPLETION_MODEL, APP_VERSION


@click.group()
@click.version_option(version=APP_VERSION)
def cli():
    """Geenii CLI tool."""
    pass


@cli.command()
@click.option("--model", "-m", default=DEFAULT_COMPLETION_MODEL, help="Model to use for completion.")
@click.option("--temperature", "-t", type=float, default=None, help="Sampling temperature.")
@click.option("--output-format", "-o", default=None, help="Output format type.")
@click.argument("prompt")
def completion(model, temperature, output_format, prompt):
    """Generate a response from a single prompt."""
    click.echo(f"Generating with prompt: {prompt}")
    # TODO: implement generation logic
    response = generate_completion(prompt=prompt, model=model, temperature=temperature, output_format=output_format)
    print(response)
    # click.echo(f"Response: {response}")
    # if response.output and len(response.output) > 0 and response.output[0].get("content", []):
    #     click.echo(f"Content: {response.output[0].get('content')[0].get('text', '')}")
    # else:
    #     click.echo("No content provided.")


@cli.command()
@click.option("--model", "-m", default=DEFAULT_COMPLETION_MODEL, help="Model to use for chat.")
@click.option("--temperature", "-t", type=float, default=None, help="Sampling temperature.")
@click.option("--output-format", "-o", default=None, help="Output format type.")
@click.argument("prompt")
def chat(model, temperature, output_format, prompt):
    """Start an interactive chat session with an initial prompt."""
    click.echo(f"Starting chat with: {prompt}")
    # TODO: implement interactive chat loop
    
    chat_history: List[ModelMessage] = []
    
    continue_chat = True
    while continue_chat:
        response = generate_chat_completion(prompt=prompt,
                                            model=model,
                                            messages=chat_history,
                                            temperature=temperature, 
                                            output_format=output_format)
        # click.echo(f"Response: {response}")
        # if response.output and len(response.output) > 0 and response.output[0].get("content", []):
        #     click.echo(f"Content: {response.output[0].get('content')[0].get('text', '')}")
        # else:
        #     click.echo("No content provided.")
        print(response)
        for msg in response.output:
            chat_history.append(msg)

        # todo check if the response contains tool calls and handle them

        prompt = click.prompt("You")


@cli.command()
@click.argument("key")
@click.argument("value")
def configure(key, value):
    """Set a configuration value."""
    click.echo(f"Setting {key} = {value}")
    # TODO: implement configuration persistence


@cli.group()
def tools():
    """Manage tools."""
    pass

@tools.command("list")
def list_tools():
    """List all registered tools."""
    click.echo("Listing tools...")

    tool_registry = get_tool_registry()

    for tool in tool_registry.list_tools():
        click.echo(f"- {tool.name}: {tool.description}")

@tools.command("show")
@click.argument("tool_name")
def show_tool(tool_name):
    """Show details for a specific tool."""
    click.echo(f"Showing details for tool: {tool_name}")

    tool_registry = get_tool_registry()
    try:
        tool = tool_registry.get(tool_name)
        click.echo(f"Name: {tool.name}")
        click.echo(f"Description: {tool.description}")
        click.echo(f"Parameters: {tool.parameters}")
    except KeyError:
        click.echo(f"Tool {tool_name} not found.")


@tools.command("call")
@click.argument("tool_name")
@click.option("--args", "-a", multiple=True, help="Arguments for the tool in key=value format.")
def call_tool(tool_name, **kwargs):
    """Call a tool by name with the provided arguments."""
    click.echo(f"Calling tool {tool_name} with arguments: {kwargs}")

    def parse_args(args):
        parsed = {}
        for arg in args:
            if "=" in arg:
                key, value = arg.split("=", 1)
                parsed[key] = value
            else:
                click.echo(f"Invalid argument format: {arg}. Expected key=value.")
        return parsed

    kwargs = parse_args(kwargs.get("args", []))

    tool_registry = get_tool_registry()
    tool_registry.invoke(tool_name, **kwargs)


if __name__ == "__main__":
    cli()
