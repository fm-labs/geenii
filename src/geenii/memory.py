import abc
import json
import sqlite3
from pathlib import Path
import logging

from geenii.datamodels import ModelMessage

logger = logging.getLogger(__name__)

class ChatMemory(abc.ABC):
    """Base class for chat memory implementations."""

    def __init__(self) -> None:
        """Initialize the chat memory."""
        self._messages: list[ModelMessage] = []

    @property
    def messages(self) -> list[ModelMessage]:
        return self._messages

    def append(self, message: ModelMessage) -> None:
        """Add a message to the memory."""
        self._messages.append(message)
        self._insert(message)

    def clear(self) -> None:
        self._messages = []
        self._write()

    @abc.abstractmethod
    def _insert(self, message: ModelMessage) -> None:
        """Insert a message into the memory storage."""
        pass

    @abc.abstractmethod
    def _write(self) -> None:
        """Save the current state of the memory to persistent storage."""
        pass

    def __iter__(self):
        return iter(self._messages)

    async def __aiter__(self):
        for message in self._messages:
            yield message


class ShortTermChatMemory(ChatMemory):
    """In-memory implementation of chat memory for short-term conversations."""

    def _insert(self, message: ModelMessage) -> None:
        # No additional action needed for in-memory storage
        pass

    def _write(self) -> None:
        # No additional action needed for in-memory storage
        pass


class FileChatMemory(ChatMemory):
    """File-based implementation of chat memory using JSONL format."""

    def __init__(self, file_path: str, create=True, restore=True) -> None:
        super().__init__()
        self.file_path = Path(file_path).resolve()
        if not create and not self.file_path.exists():
            raise FileNotFoundError(f"Chat memory file '{file_path}' does not exist.")

        # ensure the parent dir exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        if restore:
            self._read()

    def _read(self) -> None:
        file_path = self.file_path
        #self._messages = []
        if Path(file_path).exists():
            with file_path.open("r") as f:
                for line in f:
                    message_dict = json.loads(line)
                    message = ModelMessage.model_validate(message_dict)
                    self._messages.append(message)
            logger.info(f"Loaded {len(self._messages)} messages from chat memory file '{file_path}'")
        else:
            logger.info(f"No existing chat memory file found at '{file_path}', starting with empty memory")


    def _insert(self, message: ModelMessage) -> None:
        with self.file_path.open("a") as f:
            f.write(message.to_json() + "\n")
            logger.info(f"Appended message to chat memory file '{self.file_path}': {message}")

    def _write(self) -> None:
        with self.file_path.open("w") as f:
            for message in self._messages:
                f.write(message.to_json() + "\n")


# class SqliteChatMemory(ChatMemory):
#     """SQLite-based implementation of chat memory."""
#
#     def __init__(self, db_path: str) -> None:
#         super().__init__()
#         self.db_path = Path(db_path).resolve()
#
#     @property
#     def db(self) -> sqlite3.Connection:
#         return sqlite3.connect(self.db_path)
#
#     def _read(self) -> None:
#         with self.db as conn:
#             cursor = conn.cursor()
#             cursor.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT)")
#             cursor.execute("SELECT role, content FROM messages ORDER BY id")
#             rows = cursor.fetchall()
#             for role, content in rows:
#                 message = ModelMessage(role=role, content=json.loads(content))
#                 self._messages.append(message)
#
#     def _insert(self, message: ModelMessage) -> None:
#         with self.db as conn:
#             cursor = conn.cursor()
#             cursor.execute("INSERT INTO messages (role, content) VALUES (?, ?)", (message.role, json.dumps(message.content)))
#
#     def _write(self) -> None:
#         with self.db as conn:
#             cursor = conn.cursor()
#             cursor.execute("DELETE FROM messages")
#             for message in self._messages:
#                 cursor.execute("INSERT INTO messages (role, content) VALUES (?, ?)", (message.role, json.dumps(message.content)))
