import asyncio
from typing import AsyncGenerator

from geenii.ai import generate_chat_completion
from geenii.chat.chat_bots import BotInterface
from geenii.chat.chat_models import ContentPart, TextContent


class EchoBot(BotInterface):
    """
    A simple dummy bot implementation that echoes the incoming message.
    """

    def __init__(self, botname: str):
        self.botname = botname

    # spawn task that sends messages to the room every few seconds for a while to simulate a bot that keeps sending messages over time
    async def send_periodic_messages(self) -> AsyncGenerator[ContentPart, None]:
        for i in range(5):
            await asyncio.sleep(5)
            yield TextContent(text=f"Periodic message {i + 1} from bot {self.botname}")

    async def prompt(self, message: str | list[ContentPart]) -> AsyncGenerator[ContentPart, None]:
        if isinstance(message, str):
            response_text = f"You said: {message}"
        else:
            response_text = "You sent structured content"
        yield TextContent(type="text", text=f">{self.botname}< {response_text}")


class SmartBot(BotInterface):
    """
    A bot implementation with basic intelligence that uses the generate_chat_completion function
    to generate responses based on the incoming message.

    It can handle both plain text and structured content messages.
    """

    def __init__(self, botname: str):
        self.botname = botname

    async def prompt(self, message: str | list[ContentPart]) -> AsyncGenerator[ContentPart, None]:
        try:
            model_id = "ollama:mistral:latest"
            system_prompt = "You are a helpful assistant, that gives short and concise answers."
            if isinstance(message, str):
                prompt = message
            elif isinstance(message, list):
                prompt = " ".join([content.to_text() for content in message])
            else:
                raise ValueError("Unsupported message format")

            response = generate_chat_completion(
                model=model_id,
                prompt=prompt,
                system=system_prompt)

            for msg in response.output:
                for content_part in msg.content:
                    yield content_part

        except Exception:
            yield TextContent(text=f"Uuups, something went wrong :/")


def get_bot(botname: str, room_id: str = None) -> BotInterface:
    #return EchoBot(botname=botname)
    return SmartBot(botname=botname)
