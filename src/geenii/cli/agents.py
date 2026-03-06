import asyncio

import click

from geenii.agents import Agent, init_agent_registry
from geenii.hidl import HumanInTheLoopController
from geenii.chat.chat_models import TextContent
from geenii.cli.base import BaseCli


class CliHumanInTheLoopController(HumanInTheLoopController):

    async def request_tool_execution(self, tool_name: str, arguments: dict, call_id: str) -> bool:
        click.secho(f"Tool execution requested: {tool_name} with arguments {arguments} (call_id={call_id})", fg="yellow")
        response = click.prompt("Do you want to execute this tool? (y/n)", default="n")
        return response.lower() == "y"


class CliAgentRunner:

    def __init__(self, agent: Agent, interactive: bool = True):
        self.interactive = interactive
        self.agent = agent
        self.agent._hidl = CliHumanInTheLoopController()

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


class AgentsCli(BaseCli):

    def __init__(self, cli: click.core.Group):
        super().__init__(cli)
        self.agents = init_agent_registry(auto_load=True)

        @cli.group()
        def agents():
            """Manage and run agents."""
            pass

        @agents.command(name="list")
        def list_agents():
            """List all configured and loaded agents."""
            click.echo("Configured agents:")
            for agent_name in self.agents.list_configured():
                click.echo(f"- {agent_name}")

            click.echo("Loaded agents:")
            for agent_name in self.agents.list_loaded():
                click.echo(f"- {agent_name}")


        @agents.command(name="ask")
        @click.argument("prompt")
        @click.option("name", "--name", "-n", default="default", help="Name of the agent to run.")
        @click.option("continue_conversation", "--continue", "-c", is_flag=True, help="Continue the conversation after the initial prompt.")
        def ask_agent(prompt: str, name: str, continue_conversation: bool):
            """
            Run a agent with the given name and prompt.

            PROMPT  The initial prompt to start the agent with.
            """
            click.echo(f"Running agent '{name}' with prompt: {prompt}")
            g_bot = self.agents.get_instance(name)
            if not g_bot:
                click.echo(f"Agent '{name}' not found. Please check the available agents with 'agents list'.")
                return
            CliAgentRunner(g_bot, interactive=continue_conversation).run(prompt)


        @agents.command(name="inspect")
        @click.argument("name")
        def inspect_agent(name: str):
            agent_config = self.agents.get_config(name)
            if not agent_config:
                self.error(f"Agent '{name}' not found. Please check the available agents with 'agents list'.")
                return
            self.info(f"Name: {agent_config.name}")
            self.info(f"Description: {agent_config.description}")
            self.info(f"Label: {agent_config.label}")
            self.info(f"Model: {agent_config.model}")
            self.info(f"Model Parameters: {agent_config.model_parameters}")
            self.info(f"Tools: {agent_config.tools}")
            self.info(f"Skills: {agent_config.skills}")
            self.info(f"System Prompt: {agent_config.system}")
            #print(agent_config)