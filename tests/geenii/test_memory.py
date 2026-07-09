import json
import pytest

from geenii.chat_models import TextContent
from geenii.datamodels import ModelMessage
from geenii.memory import FileChatMemory


# Adjust these imports to match your project structure:
# from your_package.memory import FileChatMemory
# from your_package.models import ChatMessage, ChatMessageContent


@pytest.fixture
def tmp_json_path(tmp_path):
    return tmp_path / "chat_memory.json"


def make_message(role="user", text="hello"):
    return ModelMessage(
        role=role,
        content=[TextContent(text=text)],
    )


def test_load_messages_file_not_found_throws_file_not_found(tmp_json_path):
    with pytest.raises(FileNotFoundError):
        FileChatMemory(str(tmp_json_path), create=False)


def test_load_messages_from_existing_file(tmp_json_path):
    # Arrange: write valid JSONL (one ModelMessage JSON object per line)
    raw = [
        {
            "id": "m1",
            "role": "user",
            "content": [{"type": "text", "text": "hi"}],
        },
        {
            "id": "m2",
            "role": "assistant",
            "content": [{"type": "text", "text": "hello!"}],
        },
    ]
    lines = "\n".join(json.dumps(msg) for msg in raw) + "\n"
    tmp_json_path.write_text(lines, encoding="utf-8")

    # Act
    mem = FileChatMemory(str(tmp_json_path), create=True)
    msgs = mem.messages

    # Assert
    assert len(msgs) == 2
    assert msgs[0].id == "m1"
    assert msgs[0].role == "user"
    assert msgs[0].content[0].type == "text"
    assert msgs[0].content[0].text == "hi"
    assert msgs[1].id == "m2"
    assert msgs[1].role == "assistant"


def test_add_message_appends_and_persists(tmp_json_path):
    mem = FileChatMemory(str(tmp_json_path), create=True)
    assert mem.messages == []

    msg = make_message(role="user", text="persist me")
    mem.append(msg)

    # In-memory updated
    assert len(mem.messages) == 1
    assert mem.messages[0].role == "user"
    assert mem.messages[0].content[0].text == "persist me"

    # File updated: reload from disk and verify it round-trips
    mem2 = FileChatMemory(str(tmp_json_path), create=True)
    assert len(mem2.messages) == 1
    assert mem2.messages[0].role == "user"
    assert mem2.messages[0].content[0].text == "persist me"


def test_clear_memory_empties_and_persists(tmp_json_path):
    mem = FileChatMemory(str(tmp_json_path), create=True)
    mem.append(make_message(text="a"))
    mem.append(make_message(text="b"))
    assert len(mem.messages) == 2

    mem.clear()
    assert mem.messages == []

    # Ensure file is cleared too
    mem2 = FileChatMemory(str(tmp_json_path))
    assert mem2.messages == []


def test_save_messages_writes_valid_json(tmp_json_path):
    mem = FileChatMemory(str(tmp_json_path), create=True)
    mem.append(make_message(role="system", text="x"))

    lines = tmp_json_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    msg = json.loads(lines[0])
    assert msg["role"] == "system"
    assert msg["content"][0]["type"] == "text"
    assert msg["content"][0]["text"] == "x"
