import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest

from geenii.chat_models import TextContent, ToolCallContent
from geenii.datamodels import ModelMessage
from geenii.memory import SqliteChatMemory


@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "memory.db")


def _msg(text: str, role: str = "user") -> ModelMessage:
    return ModelMessage(role=role, content=[TextContent(text=text)])


def test_append_and_restore_round_trip(db_path):
    memory = SqliteChatMemory(db_path)
    first = _msg("hi")
    second = ModelMessage(role="assistant", content=[ToolCallContent(name="add", arguments={"a": 1}, call_id="c1")])
    memory.append(first)
    memory.append(second)
    memory.close()

    restored = SqliteChatMemory(db_path)
    assert restored.messages == [first, second]  # incl. id, timestamp and content part types


def test_used_from_another_thread(db_path):
    memory = SqliteChatMemory(db_path)

    errors = []

    def worker():
        try:
            memory.append(_msg("from thread"))
        except Exception as e:
            errors.append(e)

    t = threading.Thread(target=worker)
    t.start()
    t.join()

    assert errors == []
    assert [m.to_text() for m in SqliteChatMemory(db_path).messages] == ["from thread"]


def test_concurrent_appends_are_all_persisted(db_path):
    memory = SqliteChatMemory(db_path)

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: memory.append(_msg(f"m{i}")), range(50)))

    restored = SqliteChatMemory(db_path)
    assert sorted(m.to_text() for m in restored.messages) == sorted(f"m{i}" for i in range(50))


def test_clear_persists(db_path):
    memory = SqliteChatMemory(db_path)
    memory.append(_msg("a"))
    memory.clear()

    assert SqliteChatMemory(db_path).messages == []


def test_migrates_legacy_table(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT)")
    conn.execute("INSERT INTO messages (role, content) VALUES (?, ?)", ("user", '[{"type": "text", "text": "legacy"}]'))
    conn.commit()
    conn.close()

    memory = SqliteChatMemory(db_path)
    memory.append(_msg("new"))

    assert [m.to_text() for m in SqliteChatMemory(db_path).messages] == ["legacy", "new"]
