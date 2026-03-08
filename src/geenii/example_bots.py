from typing import AsyncGenerator

from geenii.agents import Agent
from geenii.ai import generate_chat_completion_deprecated
from geenii.chat.chat_bots import BotInterface
from geenii.chat.chat_models import ContentPart, TextContent
from geenii.datamodels import ModelMessage
from geenii.tool.registry import ToolRegistry, PythonTool


class EchoBot(BotInterface):
    """
    A simple dummy bot implementation that echoes the incoming message.
    """

    def __init__(self, botname: str):
        self.botname = botname

    # spawn task that sends messages to the room every few seconds for a while to simulate a bot that keeps sending messages over time
    # async def send_periodic_messages(self) -> AsyncGenerator[ContentPart, None]:
    #     for i in range(5):
    #         await asyncio.sleep(5)
    #         yield TextContent(text=f"Periodic message {i + 1} from bot {self.botname}")

    async def prompt(self, message: str | list[ContentPart]) -> AsyncGenerator[ModelMessage, None]:
        if isinstance(message, str):
            response_text = f"You said: {message}"
        else:
            response_text = "You sent structured content"
        yield ModelMessage(role="assistant",
                           content=[TextContent(type="text", text=f">{self.botname}< {response_text}")])


class SimpleBot(BotInterface):
    """
    A bot implementation with basic intelligence that uses the generate_chat_completion function
    to generate responses based on the incoming message.

    It can handle both plain text and structured content messages.
    """

    def __init__(self, botname: str):
        self.botname = botname

    async def prompt(self, message: str | list[ContentPart]) -> AsyncGenerator[ContentPart, None]:
        try:
            model_id = "ollama:qwen3:8b"
            system_prompt = "You are a helpful assistant, that gives short and concise answers. Always use the tools if you can. If you don't know the answer, say you don't know and don't try to make up an answer. Always use the tools if you can. If you don't know the answer, say you don't know and don't try to make up an answer."
            tools = {"get_weather", "execute_command", "file_read"}

            if isinstance(message, str):
                prompt = message
            elif isinstance(message, list):
                prompt = " ".join([content.to_text() for content in message])
            else:
                raise ValueError("Unsupported message format")

            response = generate_chat_completion_deprecated(
                model=model_id,
                prompt=prompt,
                system=system_prompt,
                messages=[],
                tools=tools,
            )

            for content_part in response.output:
                yield content_part

        except Exception:
            yield TextContent(text=f"Uuups, something went wrong :/")


class DemoAgent(Agent):
    """
    A bot implementation that demonstrates how to use tools. It registers a simple tool that gets the weather for a given location.
    """

    def __init__(self, botname: str):
        tool_registry = ToolRegistry()
        tool_registry.register(PythonTool(name="get_weather",
                                          description="Get the weather from the given location.",
                                          parameters={
                                              "type": "object",
                                              "properties": {
                                                  "location": {
                                                      "type": "string",
                                                      "description": "City and country e.g. Bogotá, Colombia"
                                                  }
                                              },
                                              "required": [
                                                  "location"
                                              ],
                                              "additionalProperties": False
                                          },
                                          handler=self.get_weather_demo))
        super().__init__(name=botname,
                         model="ollama:qwen3:8b",
                         system_prompt="You are a helpful assistant, that gives short and concise answers. Always use the tools if you can. If you don't know the answer, say you don't know and don't try to make up an answer. Always use the tools if you can. If you don't know the answer, say you don't know and don't try to make up an answer.",
                         tool_registry=tool_registry)

    @staticmethod
    def get_weather_demo(location: str) -> str:
        # Dummy implementation for testing
        return f"The current temperature in {location} is 25°C with clear skies."
