import json
import pytest

from geenii.chat.memory import FileChatMemory
from geenii.chat.models import ChatMessage, ChatMessageContent


# Adjust these imports to match your project structure:
# from your_package.memory import FileChatMemory
# from your_package.models import ChatMessage, ChatMessageContent


@pytest.fixture
def tmp_json_path(tmp_path):
    return tmp_path / "chat_memory.json"


def make_message(role="user", text="hello"):
    return ChatMessage(
        role=role,
        content=[ChatMessageContent(type="text", text=text)],
    )


def test_load_messages_file_not_found_throws_file_not_found(tmp_json_path):
    with pytest.raises(FileNotFoundError):
        FileChatMemory(str(tmp_json_path), create=False)


def test_load_messages_from_existing_file(tmp_json_path):
    # Arrange: write a valid JSON structure matching ChatMessage(**msg)
    raw = [
        {
            "id": "m1",
            "role": "user",
            "content": [
                {"id": "c1", "type": "text", "text": "hi", "data": None, "function": None, "timestamp": None}
            ],
        },
        {
            "id": "m2",
            "role": "assistant",
            "content": [
                {"id": "c2", "type": "text", "text": "hello!", "data": None, "function": None, "timestamp": None}
            ],
        },
    ]
    tmp_json_path.write_text(json.dumps({"messages": raw}), encoding="utf-8")

    # Act
    mem = FileChatMemory(str(tmp_json_path), create=True)
    msgs = mem.get_messages()

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
    assert mem.get_messages() == []

    msg = make_message(role="user", text="persist me")
    mem.add_message(msg)

    # In-memory updated
    assert len(mem.get_messages()) == 1
    assert mem.get_messages()[0].role == "user"
    assert mem.get_messages()[0].content[0].text == "persist me"

    # File updated: reload from disk and verify it round-trips
    mem2 = FileChatMemory(str(tmp_json_path), create=True)
    assert len(mem2.get_messages()) == 1
    assert mem2.get_messages()[0].role == "user"
    assert mem2.get_messages()[0].content[0].text == "persist me"


def test_clear_memory_empties_and_persists(tmp_json_path):
    mem = FileChatMemory(str(tmp_json_path), create=True)
    mem.add_message(make_message(text="a"))
    mem.add_message(make_message(text="b"))
    assert len(mem.get_messages()) == 2

    mem.clear_memory()
    assert mem.get_messages() == []

    # Ensure file is cleared too
    mem2 = FileChatMemory(str(tmp_json_path))
    assert mem2.get_messages() == []


def test_save_messages_writes_valid_json(tmp_json_path):
    mem = FileChatMemory(str(tmp_json_path), create=True)
    mem.add_message(make_message(role="system", text="x"))

    data = json.loads(tmp_json_path.read_text(encoding="utf-8"))
    assert "messages" in data
    messages = data["messages"]
    assert isinstance(messages, list)
    assert len(messages) == 1
    assert messages[0]["role"] == "system"
    assert messages[0]["content"][0]["type"] == "text"
    assert messages[0]["content"][0]["text"] == "x"
