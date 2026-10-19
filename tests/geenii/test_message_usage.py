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


# -- Agent.usage: the agent counts its model calls internally ---------------------

def test_usage_addition():
    a = Usage(input_tokens=10, output_tokens=2, cache_read_input_tokens=4)
    b = Usage(input_tokens=5, output_tokens=1, load_duration=7)
    total = a + b
    assert (total.input_tokens, total.output_tokens, total.total_tokens) == (15, 3, 18)
    assert total.cache_read_input_tokens == 4
    assert total.load_duration == 7
    assert total.cache_creation_input_tokens is None  # None on both sides stays None
    assert Usage() + Usage() == Usage()


def test_agent_counts_every_model_call(provider):
    provider.enqueue_tool_call("add", {"a": 1, "b": 2})
    provider.enqueue("3")
    agent = _agent()
    assert (agent.model_calls, agent.usage.total_tokens) == (0, 0)

    list(agent.process("1 + 2?"))
    assert agent.model_calls == 2  # tool call + answer
    assert agent.usage == Usage(input_tokens=20, output_tokens=40)

    provider.enqueue("again")
    list(agent.process("and again"))
    assert agent.model_calls == 3  # cumulative across turns
    assert agent.usage.total_tokens == 90


def test_agent_counts_skill_selection(provider):
    agent = _agent()
    from geenii.skills import SkillSpec
    for name in ("alpha", "beta"):
        agent.skills.register(SkillSpec(name=name, description=f"{name} skill", path=f"/tmp/{name}"))
    provider.enqueue('{"skill": "NONE", "confidence": 0.1, "rationale": "-"}')
    provider.enqueue("answer")

    list(agent.process("no trigger matches this"))
    assert agent.model_calls == 2  # skill selection + answer


def test_agent_counts_compaction(provider):
    provider.enqueue("the summary")
    agent = _agent()
    agent.memory.append(ModelMessage(role="user", content=[TextContent(text="hello")]))
    list(agent.process("/compact"))
    assert agent.model_calls == 1


def test_info_commands_are_not_counted(provider):
    agent = _agent()
    list(agent.process("/self"))
    assert agent.model_calls == 0


def test_handoff_adds_the_sub_agents_usage(provider, monkeypatch):
    sub = _agent()
    sub.name = "helper"
    monkeypatch.setattr(tasks_mod, "init_agent_by_name", lambda name, **kwargs: sub)
    provider.enqueue("from the helper")
    agent = _agent()

    list(agent.process("@helper do it"))
    assert sub.model_calls == 1
    assert agent.model_calls == 1
    assert agent.usage.total_tokens == 30


def test_self_shows_agent_usage(provider):
    agent = _agent()
    [before] = list(agent.process("/self"))
    assert "no model calls yet" in before.to_text()

    provider.enqueue("hi")
    list(agent.process("hello"))
    [after] = list(agent.process("/self"))
    assert "30 tokens (10 in, 20 out) in 1 model call since the agent was started" in after.to_text()
