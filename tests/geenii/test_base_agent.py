import pytest

from geenii.agent import base_agent as base_agent_mod
from geenii.agent.base import BaseTask
from geenii.agent.base_agent import BaseAgent
from geenii.chat_models import TextContent
from geenii.datamodels import ModelMessage
from geenii.memory import ShortTermChatMemory


@pytest.fixture(autouse=True)
def isolated_cache_dir(tmp_path, monkeypatch):
    """Keep agent logs out of the real cache dir."""
    monkeypatch.setattr(base_agent_mod, "GEENII_CACHE_DIR", str(tmp_path))


def _text(msg: str) -> ModelMessage:
    return ModelMessage(role="assistant", content=[TextContent(text=msg)])


class EchoTask(BaseTask):
    def __init__(self, text: str):
        self.text = text

    def execute(self):
        yield _text(self.text)


class ChainTask(BaseTask):
    """Yields a message, then enqueues the next task (if any)."""

    def __init__(self, text: str, next_task: BaseTask | None = None):
        self.text = text
        self.next_task = next_task

    def execute(self):
        yield _text(self.text)
        if self.next_task is not None:
            yield self.next_task


class RecursiveTask(BaseTask):
    """Re-enqueues itself forever."""

    def execute(self):
        yield _text("tick")
        yield RecursiveTask()


class FailingTask(BaseTask):
    def execute(self):
        raise RuntimeError("boom")
        yield  # pragma: no cover


class StubAgent(BaseAgent):
    def __init__(self, *tasks: BaseTask):
        super().__init__("test-agent", memory=ShortTermChatMemory())
        self._initial_tasks = tasks

    def _handle_message(self, message):
        for task in self._initial_tasks:
            self.enqueue_task(task)


def _run(agent: BaseAgent) -> list[str]:
    return [msg.content[0].text for msg in agent.process("hi")]


def _assert_queue_settled(agent: BaseAgent):
    assert len(agent._tasks) == 0


def test_processes_tasks_in_order():
    agent = StubAgent(EchoTask("a"), ChainTask("b", EchoTask("c")), EchoTask("d"))

    # tasks yielded by a task are appended to the end of the queue
    assert _run(agent) == ["a", "b", "d", "c"]
    _assert_queue_settled(agent)


def test_runs_exactly_max_tasks_then_stops():
    agent = StubAgent(RecursiveTask())

    msgs = _run(agent)

    assert msgs == ["tick"] * BaseAgent.MAX_TASKS + [f"Maximum number of tasks reached: {BaseAgent.MAX_TASKS}"]
    _assert_queue_settled(agent)


def test_max_tasks_drops_pending_tasks(monkeypatch):
    monkeypatch.setattr(StubAgent, "MAX_TASKS", 2)
    agent = StubAgent(EchoTask("a"), EchoTask("b"), EchoTask("c"), EchoTask("d"))

    assert _run(agent) == ["a", "b", "Maximum number of tasks reached: 2"]
    _assert_queue_settled(agent)


def test_failing_task_yields_error_and_continues():
    agent = StubAgent(FailingTask(), EchoTask("after"))

    assert _run(agent) == ["An error occurred while processing the task: boom", "after"]
    _assert_queue_settled(agent)


def test_failing_task_logs_its_own_name(caplog):
    agent = StubAgent(EchoTask("before"), FailingTask())

    _run(agent)

    errors = [r.getMessage() for r in caplog.records if r.levelname == "ERROR"]
    assert any("Error processing task FailingTask" in e for e in errors)


def test_agent_runs_llm_tool_call_round_trip(monkeypatch):
    """End-to-end through the real Agent: LLM requests a tool call, the tool runs, the LLM answers."""
    from geenii.agent import tasks as tasks_mod
    from geenii.agents import Agent
    from geenii.chat_models import ToolCallContent, ToolCallResultContent
    from geenii.provider.fake.provider import FakeProvider
    from geenii.skills import SkillRegistry
    from geenii.tool.python import PythonFunctionTool
    from geenii.tool.registry import ToolRegistry

    provider = FakeProvider()
    provider.enqueue_tool_call("add", {"a": 2, "b": 3})
    provider.enqueue("The answer is 5.")
    monkeypatch.setattr(tasks_mod, "generate_chat_completion",
                        lambda request, **kwargs: provider.generate_chat_completion(request))

    registry = ToolRegistry()
    registry.register(PythonFunctionTool(name="add", handler=lambda a, b: a + b))
    skills = SkillRegistry()
    skills.skills.clear()
    agent = Agent("test-agent", model="fake:test", allowed_tools={"add"}, memory=ShortTermChatMemory(),
                  tool_registry=registry, skill_registry=skills)

    msgs = list(agent.process("what is 2 + 3?"))

    parts = [m.content[0] for m in msgs]
    assert any(isinstance(p, ToolCallResultContent) and p.result == "5" for p in parts)
    assert isinstance(parts[-1], TextContent) and parts[-1].text == "The answer is 5."
    assert not any(isinstance(p, ToolCallContent) for p in parts)
    _assert_queue_settled(agent)


def test_initialize_runs_lazily_once_after_subclass_init():
    """Subclasses may set attributes after super().__init__(); _initialize() must not run before that."""

    class LateAttrAgent(StubAgent):
        def __init__(self):
            super().__init__(EchoTask("ok"))
            self.dependency = "ready"
            self.init_calls = []

        def _initialize(self):
            if self._initialized:
                return
            self.init_calls.append(self.dependency)
            self._initialized = True

    agent = LateAttrAgent()
    assert agent.init_calls == []

    _run(agent)
    _run(agent)
    assert agent.init_calls == ["ready"]


def test_process_manager_agent_can_be_constructed():
    from geenii.agents import ProcessManagerAgent

    ProcessManagerAgent("pm", memory=ShortTermChatMemory())
