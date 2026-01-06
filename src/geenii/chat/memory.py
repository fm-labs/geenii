import abc
import json
import time
from pathlib import Path

from geenii.chat.models import ChatMessage


class ChatMemory(abc.ABC):
    """Base class for chat memory implementations."""

    @abc.abstractmethod
    def add_message(self, message: ChatMessage) -> None:
        """Add a message to the memory."""
        raise NotImplementedError("This method should be overridden by subclasses.")

    def add_messages(self, messages: list[ChatMessage]) -> None:
        """Add multiple messages to the memory."""
        for message in messages:
            self.add_message(message)

    @abc.abstractmethod
    def get_messages(self) -> list[ChatMessage]:
        """Retrieve all messages from the memory."""
        raise NotImplementedError("This method should be overridden by subclasses.")

    @abc.abstractmethod
    def clear_memory(self) -> None:
        """Clear all messages from the memory."""
        raise NotImplementedError("This method should be overridden by subclasses.")


class FileChatMemory(ChatMemory):
    """File-based implementation of chat memory."""

    def __init__(self, file_path: str, create=False) -> None:
        self.file_path = file_path
        if not create and not Path(file_path).exists():
            raise FileNotFoundError(f"Chat memory file '{file_path}' does not exist.")

        # ensure the parent dir exists
        Path(file_path).parent.mkdir(parents=True, exist_ok=True)
        self.messages = []
        if Path(file_path).exists():
            self.restore()

    def save(self) -> None:
        with open(self.file_path, 'w') as f:
            data = {
                "messages": [msg.model_dump() for msg in self.messages],
                "last_updated": int(time.time() * 1000)
            }
            json.dump(data, f, indent=2)

    def restore(self) -> None:
        try:
            with open(self.file_path, 'r') as f:
                data = json.load(f)
                self.messages = [ChatMessage(**msg) for msg in data["messages"]]
        except FileNotFoundError:
            return None

    def add_message(self, message: ChatMessage) -> None:
        self.messages.append(message)
        self.save()

    def get_messages(self) -> list[ChatMessage]:
        return self.messages

    def clear_memory(self) -> None:
        self.messages = []
        self.save()