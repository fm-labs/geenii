import asyncio

import click

from geenii.chat.chat_models import TextContent
from geenii.cli.base import BaseCli
from geenii.wizards import init_wizard_by_name, Wizard, HumanInTheLoopHandler


class CliHumanInTheLoopHandler(HumanInTheLoopHandler):

    async def request_tool_execution(self, tool_name: str, arguments: dict, call_id: str) -> bool:
        click.secho(f"Tool execution requested: {tool_name} with arguments {arguments} (call_id={call_id})", fg="yellow")
        response = click.prompt("Do you want to execute this tool? (y/n)", default="n")
        return response.lower() == "y"


class CliBotRunner:

    def __init__(self, bot: Wizard, interactive: bool = True):
        self.interactive = interactive
        self.bot = bot
        self.bot._hidl = CliHumanInTheLoopHandler()

        print("Bot initialized. Starting interaction...")
        print(bot)


    def run(self, prompt: str):
        asyncio.run(self._run(prompt))

    async def _run(self, prompt: str):
        while prompt.lower() != "exit" and len(prompt) > 0:
            async for msg in self.bot.prompt([TextContent(text=prompt)]):
                for part in msg.content:
                    click.secho(f">>> [{part.type}] {part.to_text()}", fg="cyan")

            if self.interactive:
                prompt = click.prompt("> ", default="", show_default=False)
            else:
                break




class WizardsCli(BaseCli):

    def __init__(self, cli: click.core.Group):
        super().__init__(cli)

        @cli.group()
        def wizards():
            """Manage and run wizards."""
            pass

        @wizards.command()
        @click.argument("prompt")
        @click.option("name", "--name", "-n", default="default", help="Name of the wizard to run.")
        def ask(prompt: str, name: str):
            """
            Run a wizard with the given name and prompt.

            PROMPT  The initial prompt to start the wizard with.
            """
            click.echo(f"Running wizard '{name}' with prompt: {prompt}")
            g_bot = init_wizard_by_name(name)
            #g_bot.load_skill("mac-skills")
            CliBotRunner(g_bot).run(prompt)
