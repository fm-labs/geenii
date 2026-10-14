import json

import pytest

from geenii.agent import base_agent as base_agent_mod
from geenii.agent import info_commands
from geenii.agents import Agent
from geenii.chat_models import TextContent
from geenii.datamodels import AIModelInfo, ModelMessage
from geenii.memory import ShortTermChatMemory


@pytest.fixture(autouse=True)
def isolated_cache_dir(tmp_path, monkeypatch):
    """Keep agent logs out of the real cache dir, and read usage logs from it."""
    monkeypatch.setattr(base_agent_mod, "CACHE_DIR", str(tmp_path))
    monkeypatch.setattr(info_commands, "CACHE_DIR", str(tmp_path))
    return tmp_path


def _agent(context_id="ctx", allowed_tools=None) -> Agent:
    memory = ShortTermChatMemory()
    memory.append(ModelMessage(role="user", content=[TextContent(text="hello")]))
    memory.append(ModelMessage(role="assistant", content=[TextContent(text="hi there")]))
    return Agent(name="tester", model="fake:test", description="A test agent",
                 allowed_tools=allowed_tools, context_id=context_id, memory=memory)


def _run(agent: Agent, prompt: str) -> str:
    messages = list(agent.process(prompt))
    assert len(messages) == 1
    assert messages[0].role == "assistant"
    return messages[0].to_text()


def test_info_commands_are_builtin_commands():
    for name in ("self", "usage", "models", "tools", "context", "help"):
        assert name in Agent.BUILTIN_COMMANDS


@pytest.mark.parametrize("command", ["self", "usage", "tools", "context", "help"])
def test_info_reply_is_not_stored_in_memory(command):
    agent = _agent()
    _run(agent, f"/{command}")
    assert len(agent.message_history) == 2


def test_self():
    text = _run(_agent(allowed_tools={"bash"}), "/self")
    assert "### tester" in text
    assert "`fake:test`" in text
    assert "`ctx`" in text
    assert "1 allowed" in text


def test_usage_sums_conversation_and_compactions(isolated_cache_dir):
    logs = isolated_cache_dir / "logs"
    logs.mkdir()
    entries = [
        {"provider": "fake", "model": "test", "context_id": "ctx", "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}},
        {"provider": "fake", "model": "test", "context_id": "ctx-1", "usage": {"input_tokens": 20, "output_tokens": 5, "total_tokens": 25}},
        {"provider": "fake", "model": "test", "context_id": "ctxother", "usage": {"input_tokens": 999, "output_tokens": 999, "total_tokens": 1998}},
    ]
    (logs / "ai-usage-2026-10.log").write_text("\n".join(json.dumps(e) for e in entries) + "\nnot json ctx\n")

    text = _run(_agent(context_id="ctx-2"), "/usage")
    assert "| `fake:test` | 2 | 30 | 10 | 40 |" in text
    assert "999" not in text


def test_usage_by_purpose(isolated_cache_dir):
    logs = isolated_cache_dir / "logs"
    logs.mkdir()
    usage = {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}
    entries = [
        {"provider": "fake", "model": "test", "context_id": "ctx", "source": "agent:tester", "task": "llm", "usage": usage},
        {"provider": "fake", "model": "test", "context_id": "ctx", "source": "agent:tester", "task": "llm", "usage": usage},
        {"provider": "fake", "model": "test", "context_id": "ctx", "source": "agent:tester", "task": "skill_select", "usage": usage},
        {"provider": "fake", "model": "test", "context_id": "ctx", "usage": usage},  # written before tagging
    ]
    (logs / "ai-usage-2026-10.log").write_text("\n".join(json.dumps(e) for e in entries) + "\n")

    text = _run(_agent(), "/usage")
    assert "| `fake:test` | 4 | 40 | 20 | 60 |" in text
    assert "**By purpose**" in text
    assert "| llm | 2 | 20 | 10 | 30 |" in text
    assert "| skill_select | 1 | 10 | 5 | 15 |" in text
    assert "| untagged | 1 | 10 | 5 | 15 |" in text
    assert "| **Total** | 4 | 40 | 20 | 60 |" in text


def test_usage_hides_purpose_table_for_a_single_task(isolated_cache_dir):
    logs = isolated_cache_dir / "logs"
    logs.mkdir()
    entry = {"provider": "fake", "model": "test", "context_id": "ctx", "task": "llm",
             "usage": {"input_tokens": 1, "output_tokens": 1, "total_tokens": 2}}
    (logs / "ai-usage-2026-10.log").write_text(json.dumps(entry) + "\n")
    assert "By purpose" not in _run(_agent(), "/usage")


def test_usage_counts_failed_calls(isolated_cache_dir):
    logs = isolated_cache_dir / "logs"
    logs.mkdir()
    entries = [
        {"provider": "fake", "model": "test", "context_id": "ctx", "task": "llm",
         "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15}, "error": None},
        {"provider": "fake", "model": "test", "context_id": "ctx", "task": "llm", "usage": {},
         "error": "RuntimeError: provider down"},
    ]
    (logs / "ai-usage-2026-10.log").write_text("\n".join(json.dumps(e) for e in entries) + "\n")

    text = _run(_agent(), "/usage")
    assert "| `fake:test` | 2 | 10 | 5 | 15 |" in text
    assert "1 of 2 calls failed" in text


def test_usage_without_calls():
    assert "No model calls" in _run(_agent(), "/usage")


def test_models_marks_current(monkeypatch):
    import geenii.ai
    monkeypatch.setattr(geenii.ai, "enumerate_models", lambda: [
        AIModelInfo(provider="fake", name="test", locality="local"),
        AIModelInfo(provider="fake", name="other", locality="local"),
    ])
    text = _run(_agent(), "/models")
    assert "**`test`**" in text
    assert "`other`" in text


def test_tools_lists_builtin_and_missing():
    text = _run(_agent(allowed_tools={"bash", "mcp__nope__thing"}), "/tools")
    assert "`bash`" in text
    assert "Not available" in text and "`mcp__nope__thing`" in text


def test_context_counts_messages_and_compactions():
    text = _run(_agent(context_id="ctx-3"), "/context")
    assert "**Compactions:** 3" in text
    assert "2 (1 assistant, 1 user)" in text


def test_help_lists_commands():
    text = _run(_agent(), "/help")
    for name in Agent.BUILTIN_COMMANDS:
        assert f"`/{name}`" in text


def test_usage_tolerates_malformed_usage(isolated_cache_dir):
    logs = isolated_cache_dir / "logs"
    logs.mkdir()
    entries = [
        {"provider": "fake", "model": "test", "context_id": "ctx", "usage": {"input_tokens": "lots"}},
        {"provider": "fake", "model": "test", "context_id": "ctx", "usage": {"input_tokens": 1, "output_tokens": 1}},
    ]
    (logs / "ai-usage-2026-10.log").write_text("\n".join(json.dumps(e) for e in entries) + "\n")

    # the malformed call is counted without tokens; a missing total is input + output
    assert "| `fake:test` | 2 | 1 | 1 | 2 |" in _run(_agent(), "/usage")


def test_usage_reports_cache_share_across_versions(isolated_cache_dir):
    logs = isolated_cache_dir / "logs"
    logs.mkdir()
    entries = [
        # version 1 anthropic line: input_tokens left out the 600 cached tokens
        {"provider": "anthropic", "model": "m", "context_id": "ctx",
         "usage": {"input_tokens": 100, "output_tokens": 10, "total_tokens": 110,
                   "cache_creation_input_tokens": 300, "cache_read_input_tokens": 300}},
        # version 2 line
        {"provider": "anthropic", "model": "m", "context_id": "ctx", "usage_version": 2,
         "usage": {"input_tokens": 1000, "output_tokens": 10, "total_tokens": 1010,
                   "cache_creation_input_tokens": 0, "cache_read_input_tokens": 900}},
    ]
    (logs / "ai-usage-2026-10.log").write_text("\n".join(json.dumps(e) for e in entries) + "\n")

    text = _run(_agent(), "/usage")
    assert "| `anthropic:m` | 2 | 1700 | 20 | 1720 |" in text
    assert "1,200 of 1,700 input tokens (70%) were read from the prompt cache; 300 were written to it." in text
