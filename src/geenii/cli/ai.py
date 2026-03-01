from typing import List

import click

from geenii.ai import generate_completion, generate_chat_completion_deprecated
from geenii.chat.chat_models import TextContent
from geenii.cli.base import BaseCli
from geenii.config import DEFAULT_COMPLETION_MODEL
from geenii.core.core_tools import execute_command
from geenii.datamodels import ModelMessage
from geenii.tools import ToolRegistry, PythonTool
from geenii.wizards import DEFAULT_WIZARD_SYSTEM_PROMPT


class AiCli(BaseCli):

    def __init__(self, cli: click.core.Group):
        super().__init__(cli)

        @cli.group()
        def ai():
            """Run AI inference commands."""
            pass


        @ai.command()
        @click.option("--model", "-m", default=DEFAULT_COMPLETION_MODEL, help="Model to use for completion.")
        @click.option("--temperature", "-t", type=float, default=None, help="Sampling temperature.")
        @click.option("--output-format", "-o", default=None, help="Output format type.")
        @click.argument("prompt")
        def completion(model, temperature, output_format, prompt):
            """Generate a response from a single prompt."""
            click.echo(f"Generating with prompt: {prompt}")
            response = generate_completion(prompt=prompt, model=model, temperature=temperature,
                                           output_format=output_format)
            print(response)

        @ai.command()
        @click.option("--model", "-m", default=DEFAULT_COMPLETION_MODEL, help="Model to use for chat.")
        @click.option("--temperature", "-t", type=float, default=None, help="Sampling temperature.")
        @click.option("--output-format", "-o", default=None, help="Output format type.")
        @click.argument("prompt")
        def chat(model, temperature, output_format, prompt):
            """Start an interactive chat session with an initial prompt."""
            click.echo(f"YOU: {prompt}")

            memory: List[ModelMessage] = []

            # Initialize chat history
            memory.append(ModelMessage(role="user", content=[TextContent(text="My name is Danny"), ]))
            memory.append(
                ModelMessage(role="assistant", content=[TextContent(text="Nice to meet you Danny, I am Ozzy"), ]))
            memory.append(ModelMessage(role="user", content=[
                TextContent(text="My car is red and I live in Berlin, but i lived in New York before"), ]))
            memory.append(ModelMessage(role="user", content=[TextContent(text="I love to eat sushi"), ]))

            tool_registry = ToolRegistry()
            tool_registry.register(PythonTool(name="execute_command",
                                              description="Execute a shell command on the user's computer and return the output.",
                                              parameters={"command": {"type": "string",
                                                                      "description": "The shell command to execute."}},
                                              handler=execute_command))
            tool_registry.register(
                PythonTool(name="get_weather", description="Get the weather from the given location.",
                           parameters={"location": {"type": "string"}},
                           handler=lambda x: f"The weather in {x['location']} is sunny with a high of 25°C."))

            continue_chat = True
            while continue_chat:
                if not prompt or prompt.lower() in {"exit", "quit"}:
                    click.echo("No input provided. Ending chat session.")
                    break

                # generate a response based on the chat history
                response = generate_chat_completion_deprecated(prompt=prompt,
                                                               model=model,
                                                               system=DEFAULT_WIZARD_SYSTEM_PROMPT,
                                                               messages=memory,
                                                               tool_registry=tool_registry,
                                                               tools={"get_weather", "execute_command"},
                                                               temperature=temperature,
                                                               output_format=output_format)
                # print the assistant response
                # print(response)

                # add the assistant response to the chat history
                memory.append(ModelMessage(role="user", content=[TextContent(text=prompt), ]))
                memory.append(ModelMessage(role="assistant", content=response.output))

                echo_model_messages(memory[-1:])  # print the last assistant message

                # prompt the user for the next message
                prompt = click.prompt("YOU> ", default="", show_default=False)


def echo_model_messages(messages: List[ModelMessage]):
    output = ""
    for msg in messages:
        role = msg.role
        content = "\n".join([part.to_text() for part in msg.content])
        output += f"{role}: {content}\n"
    click.echo(output)
