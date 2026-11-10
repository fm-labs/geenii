"""
Every model call an agent task makes carries the agent's context id, so its usage is attributed to the conversation,
and is tagged with the agent as `source` and the purpose as `task` for the usage log.
"""

import pytest

from geenii.agent import base_agent as base_agent_mod
from geenii.agent import tasks
from geenii.agent.registry import AgentRegistry, AgentSpec
from geenii.agents import Agent
from geenii.chat_models import TextContent
from geenii.datamodels import ModelMessage
from geenii.memory import ShortTermChatMemory
from geenii.skills import SkillSpec
from geenii.tool.registry import ToolRegistry


class StopTask(Exception):
    pass


@pytest.fixture(autouse=True)
def isolated_cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(base_agent_mod, "GEENII_CACHE_DIR", str(tmp_path))


@pytest.fixture
def requests(monkeypatch):
    """Capture the completion request and stop the task there."""
    captured = []

    def fake_generate_chat_completion(request, tool_registry=None, **tags):
        captured.append((request, tags))
        raise StopTask()

    monkeypatch.setattr(tasks, "generate_chat_completion", fake_generate_chat_completion)
    return captured


@pytest.fixture
def agent():
    memory = ShortTermChatMemory()
    memory.append(ModelMessage(role="user", content=[TextContent(text="hello")]))
    agent = Agent(name="tester", model="fake:test", context_id="ctx-1", memory=memory)
    for name in ("alpha", "beta"):
        agent.skills.register(SkillSpec(name=name, description=f"The {name} skill", path=f"/tmp/{name}"))
    return agent


def _run(task, requests, expected_task: str):
    with pytest.raises(StopTask):
        list(task.execute())
    request, tags = requests[0]
    assert request.context_id == "ctx-1"
    assert tags == {"source": "agent:tester", "task": expected_task}


def test_llm_task(agent, requests):
    _run(tasks.LLMTask(agent, message="hi"), requests, "llm")


def test_find_best_skill_task(agent, requests):
    _run(
        tasks.FindBestSkillTask(agent, prompt="no trigger matches this"),
        requests,
        "skill_select",
    )


def test_find_best_agent_task(agent, requests, monkeypatch):
    registry = AgentRegistry()
    registry.configs["other"] = AgentSpec(name="other", model="fake:test")
    monkeypatch.setattr(tasks, "init_global_agent_registry", lambda: registry)
    _run(
        tasks.FindBestAgentTask(agent, prompt="who should answer?"),
        requests,
        "agent_select",
    )


def test_tool_filter_task(agent, requests):
    _run(
        tasks.ToolFilterTask(agent, prompt="pick tools", tool_registry=ToolRegistry()),
        requests,
        "tool_filter",
    )


def test_memory_compaction_task_uses_the_compacted_context(agent, requests):
    # the context being compacted; the rotation to "ctx-2" happens after the call
    _run(tasks.MemoryCompactionTask(agent, prompt=""), requests, "compact")
