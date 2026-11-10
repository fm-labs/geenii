import abc
import json
import logging
import sqlite3
import threading
from pathlib import Path

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

    @abc.abstractmethod
    def _write(self) -> None:
        """Save the current state of the memory to persistent storage."""

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
        # self._messages = []
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


class SqliteChatMemory(ChatMemory):
    """
    SQLite-based implementation of chat memory.

    The connection may be used from any thread (e.g. an agent created in one thread and run in a
    server threadpool); access is serialized with a lock.
    """

    def __init__(self, db_path: str, restore: bool = True) -> None:
        super().__init__()
        self.db_path = Path(db_path).resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        with self._lock, self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, message TEXT)"
            )
            # migrate tables created before the 'message' column existed
            columns = {row[1] for row in self._conn.execute("PRAGMA table_info(messages)")}
            if "message" not in columns:
                self._conn.execute("ALTER TABLE messages ADD COLUMN message TEXT")
        if restore:
            self._read()

    def _read(self) -> None:
        with self._lock:
            rows = self._conn.execute("SELECT role, content, message FROM messages ORDER BY id").fetchall()
        for role, content, message_json in rows:
            if message_json:
                message = ModelMessage.model_validate_json(message_json)
            else:
                message = ModelMessage.model_validate({"role": role, "content": json.loads(content)})
            self._messages.append(message)

    @staticmethod
    def _row(message: ModelMessage) -> tuple[str, str, str]:
        content = json.dumps(message.model_dump(mode="json")["content"])
        return message.role, content, message.to_json()

    def _insert(self, message: ModelMessage) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO messages (role, content, message) VALUES (?, ?, ?)",
                self._row(message),
            )

    def _write(self) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM messages")
            self._conn.executemany(
                "INSERT INTO messages (role, content, message) VALUES (?, ?, ?)",
                [self._row(message) for message in self._messages],
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()
