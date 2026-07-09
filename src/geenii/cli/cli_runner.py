import asyncio

import click

from geenii.agents import Agent
from geenii.hitl import HumanInTheLoopController


class CliHumanInTheLoopController(HumanInTheLoopController):

    async def request_tool_execution(self, tool_name: str, arguments: dict, call_id: str) -> bool:
        click.secho(f"Tool execution requested: {tool_name} with arguments {arguments} (call_id={call_id})",
                    fg="yellow")

        #asyncio.create_task(asyncio.to_thread(
        #    tts_say_cli(f"A tool call was requested: {tool_name} with {len(arguments)} arguments. Do you approve?")))

        response = click.prompt("Do you approve? (y/n)", default="n")
        return response.lower() == "y"


class CliAgentRunner:

    def __init__(self, agent: Agent, interactive: bool = True):
        self.interactive = interactive
        self.agent = agent
        # self.agent._hitl = CliHumanInTheLoopController()

        print("Bot initialized. Starting interaction...")
        print(agent)

    def run(self, prompt: str):
        asyncio.run(self._run(prompt))

    async def _run(self, prompt: str):
        while prompt.lower() != "exit" and len(prompt) > 0:
            async for msg in self.agent.prompt(prompt):
                for part in msg.content:
                    click.secho(f">>> [{part.type}] {part.to_text()}", fg="cyan")

            if self.interactive:
                prompt = click.prompt("> ", default="", show_default=False)
            else:
                break
