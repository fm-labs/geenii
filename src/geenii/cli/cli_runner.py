import time
from queue import Queue, Empty, ShutDown

import click
import logging

from geenii.agents import Agent
from geenii.hitl import HumanInTheLoopController

logger = logging.getLogger(__name__)


class CliHumanInTheLoopController(HumanInTheLoopController):
    def request_tool_execution(self, tool_name: str, arguments: dict, call_id: str) -> bool:
        click.secho(
            f"Tool execution requested: {tool_name} with arguments {arguments} (call_id={call_id})",
            fg="yellow",
        )

        # threading.Thread(target=tts_say_cli,
        #    args=(f"A tool call was requested: {tool_name} with {len(arguments)} arguments. Do you approve?",)).start()

        response = click.prompt("Do you approve? (y/n)", default="n")
        return response.lower() == "y"


class CliAgentRunner:
    def __init__(self, agent: Agent, interactive: bool = True):
        self.interactive = interactive
        self.agent = agent
        # self.agent._hitl = CliHumanInTheLoopController()

        logger.debug("Bot initialized. Starting interaction...")
        logger.debug(agent)

    def run(self, prompt: str):
        while prompt.lower() != "exit" and len(prompt) > 0:
            for msg in self.agent.process(prompt):
                for part in msg.content:
                    click.secho(f">>> [{part.type}] {part.to_text()}", fg="cyan")

            if self.interactive:
                prompt = click.prompt("> ", default="", show_default=False)
            else:
                break


class AutonomousAgentRunner:
    def __init__(self, agent: Agent, queue: Queue):
        self.queue = queue
        self.agent = agent
        # self.agent._hitl = NoHumanInTheLoopController()

        logger.debug("Bot initialized. Starting interaction...")
        logger.debug(agent)

    def run(self, prompt: str):

        while True:
            try:
                prompt = self.queue.get(timeout=10)  # blocks until an item is available
            except Empty:
                print("No new messages")
                time.sleep(10)
                continue
            except ShutDown:
                print("Shutdown detected")
                break

            if prompt is None or prompt == "exit":  # sentinel value tells the worker to stop
                print("Received exit trigger", prompt)
                self.queue.task_done()
                break

            try:
                print("==> Received message:", prompt)
                for msg in self.agent.process(prompt):
                    for part in msg.content:
                        click.secho(f">>> [{part.type}] {part.to_text()}", fg="cyan")
            finally:
                self.queue.task_done()  # mark this item as handled

        print("Exiting...")