"""ModelMessage.usage: the usage of a model call is on the first message created from its response, and only there."""
import pytest

from geenii.agent import base_agent as base_agent_mod
from geenii.agent import tasks as tasks_mod
from geenii.agents import Agent
from geenii.chat_models import TextContent, ToolCallContent
from geenii.datamodels import ModelMessage, Usage
from geenii.memory import FileChatMemory, ShortTermChatMemory
from geenii.provider.fake.provider import FakeProvider
from geenii.skills import SkillRegistry
from geenii.tool.python import PythonFunctionTool
from geenii.tool.registry import ToolRegistry


@pytest.fixture(autouse=True)
def isolated_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(base_agent_mod, "CACHE_DIR", str(tmp_path))


@pytest.fixture
def provider(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr(tasks_mod, "generate_chat_completion",
                        lambda request, **kwargs: provider.generate_chat_completion(request))
    return provider


def _agent() -> Agent:
    registry = ToolRegistry()
    registry.register(PythonFunctionTool(name="add", handler=lambda a, b: a + b))
    skills = SkillRegistry()
    skills.skills.clear()
    return Agent("tester", model="fake:test", allowed_tools={"add"}, memory=ShortTermChatMemory(),
                 tool_registry=registry, skill_registry=skills)


def _total(messages) -> int:
    return sum(m.usage.total_tokens for m in messages if m.usage)


def test_final_answer_carries_usage(provider):
    provider.enqueue("hello")
    agent = _agent()

    [reply] = list(agent.process("hi"))

    assert reply.usage == Usage(input_tokens=10, output_tokens=20)
    user, assistant = agent.message_history
    assert user.usage is None
    assert assistant.usage.total_tokens == 30  # stored with the message


def test_usage_is_counted_once_per_model_call(provider):
    # call 1: two parallel tool calls in one response; call 2: the answer
    provider.enqueue_parts([
        ToolCallContent(name="add", arguments={"a": 1, "b": 2}, call_id="c1"),
        ToolCallContent(name="add", arguments={"a": 3, "b": 4}, call_id="c2"),
    ])
    provider.enqueue("3 and 7")
    agent = _agent()

    list(agent.process("add things"))

    history = agent.message_history
    tool_calls = [m for m in history if isinstance(m.content[0], ToolCallContent)]
    assert [m.usage is not None for m in tool_calls] == [True, False]  # only the response's first message
    assert all(m.usage is None for m in history if m.role in ("user", "tool"))
    assert history[-1].usage is not None
    assert _total(history) == 2 * 30  # two model calls


def test_usage_survives_file_memory(tmp_path):
    path = tmp_path / "memory.jsonl"
    memory = FileChatMemory(str(path))
    memory.append(ModelMessage(role="assistant", content=[TextContent(text="hi")],
                               usage=Usage(input_tokens=5, output_tokens=1, cache_read_input_tokens=4)))

    [restored] = FileChatMemory(str(path)).messages
    assert restored.usage == Usage(input_tokens=5, output_tokens=1, cache_read_input_tokens=4)


def test_messages_without_usage_still_load():
    old = {"type": "message", "role": "assistant", "content": [{"type": "text", "text": "hi"}]}
    assert ModelMessage.model_validate(old).usage is None


def test_compaction_summary_carries_usage(provider):
    provider.enqueue("the summary")
    agent = _agent()
    agent.memory.append(ModelMessage(role="user", content=[TextContent(text="hello")]))

    [summary] = list(tasks_mod.MemoryCompactionTask(agent, prompt="").execute())

    assert summary.usage.total_tokens == 30
