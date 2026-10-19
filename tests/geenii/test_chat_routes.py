import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from geenii.agent import base_agent as base_agent_mod
from geenii.agent import tasks as tasks_mod
from geenii import g as g_mod
from geenii.agent.registry import AgentRegistry, AgentSpec
from geenii.chat_models import ToolCallResultContent, UserInteractionContent
from geenii.datamodels import ChatMessageEvent
from geenii.hitl import WebHumanInTheLoopController
from geenii.provider.fake.provider import FakeProvider
from geenii.server import chat_routes
from geenii.server.chat_sessions import ChatSessionStore
from geenii.server.server import app
from geenii.server.web_runner import AgentBusyError
from geenii.tool.python import PythonFunctionTool
from geenii.tool.registry import ToolRegistry


@pytest.fixture(autouse=True)
def isolated_cache_dir(tmp_path, monkeypatch):
    """Keep agent logs out of the real cache dir."""
    monkeypatch.setattr(base_agent_mod, "GEENII_CACHE_DIR", str(tmp_path / "cache"))


@pytest.fixture
def provider(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr(tasks_mod, "generate_chat_completion",
                        lambda request, **kwargs: provider.generate_chat_completion(request))
    return provider


@pytest.fixture
def add_tool(monkeypatch):
    """Agents created by the store get a tool registry with an `add` tool."""
    calls = []

    def add(a, b):
        calls.append((a, b))
        return int(a) + int(b)

    def make_registry():
        registry = ToolRegistry()
        registry.register(PythonFunctionTool(name="add", handler=add))
        return registry

    monkeypatch.setattr(g_mod, "ToolRegistry", make_registry)
    return calls


@pytest.fixture
def store(tmp_path):
    agents = AgentRegistry()
    agents.configs.update({
        "default": AgentSpec(name="default", model="fake:test", tools=["add"]),
        "other": AgentSpec(name="other", model="fake:test"),
    })
    return ChatSessionStore(tmp_path / "chats", agents, approval_timeout=5)


@pytest.fixture
def client(store):
    app.dependency_overrides[chat_routes.dep_chat_sessions] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.pop(chat_routes.dep_chat_sessions, None)


def _create(client, agent="default") -> str:
    response = client.post("/api/v1/chats", json={"agent": agent})
    assert response.status_code == 201
    return response.json()["id"]


def _events(response) -> list[dict]:
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    return [json.loads(line) for line in response.text.splitlines() if line]


def _texts(events) -> list[str]:
    return [p["text"] for e in events if e["type"] == "message"
            for p in e["message"]["message"]["content"] if p["type"] == "text"]


# -- sessions ------------------------------------------------------------------


def test_create_list_get_delete(client, store):
    first = _create(client)
    second = _create(client, "other")

    listed = client.get("/api/v1/chats").json()
    assert {s["id"] for s in listed} == {first, second}
    assert client.get(f"/api/v1/chats/{first}").json()["agent"] == "default"

    assert client.delete(f"/api/v1/chats/{first}").status_code == 204
    assert client.get(f"/api/v1/chats/{first}").status_code == 404
    assert not (store.base_dir / first).exists()
    assert [s["id"] for s in client.get("/api/v1/chats").json()] == [second]


def test_list_ignores_dirs_without_meta_and_missing_base_dir(client, store):
    assert client.get("/api/v1/chats").json() == []
    (store.base_dir / "ai-routes-session").mkdir(parents=True)
    (store.base_dir / "ai-routes-session" / "memory.jsonl").write_text("")
    assert client.get("/api/v1/chats").json() == []


def test_create_rejects_unknown_agent(client):
    response = client.post("/api/v1/chats", json={"agent": "nope"})
    assert response.status_code == 400
    assert "nope" in response.json()["detail"]


@pytest.mark.parametrize("context_id", ["..", "a.b", "x" * 65, "with space", "%2e%2e"])
def test_rejects_unsafe_context_id(client, store, tmp_path, context_id):
    response = client.post(f"/api/v1/chats/{context_id}/messages", json={"prompt": "hi"})
    assert 400 <= response.status_code < 500  # ".." is already normalized away by the client (405)
    assert not any(p.name == "memory.jsonl" for p in tmp_path.rglob("*"))


def test_unknown_chat_is_404(client):
    assert client.post("/api/v1/chats/abc/messages", json={"prompt": "hi"}).status_code == 404
    assert client.get("/api/v1/chats/abc/messages").status_code == 404


def test_message_requires_input(client):
    chat = _create(client)
    assert client.post(f"/api/v1/chats/{chat}/messages", json={"prompt": "  "}).status_code == 422


def test_files_endpoints_are_501(client):
    chat = _create(client)
    assert client.get(f"/api/v1/chats/{chat}/files").status_code == 501
    assert client.post(f"/api/v1/chats/{chat}/files").status_code == 501


# -- messages ------------------------------------------------------------------


def test_post_message_streams_turn_and_stores_history(client, provider):
    chat = _create(client)
    provider.enqueue("Hello there.")

    events = _events(client.post(f"/api/v1/chats/{chat}/messages", json={"prompt": "hi"}))

    assert events[0] == {"type": "status", "status": "thinking"}
    assert events[-1] == {"type": "done"}
    assert _texts(events) == ["Hello there."]
    message = next(e["message"] for e in events if e["type"] == "message")
    assert message["sender_id"] == "default"
    assert message["context_id"] == chat
    assert message["id"] == message["message"]["id"]

    history = client.get(f"/api/v1/chats/{chat}/messages").json()
    assert [(m["sender_id"], m["message"]["role"]) for m in history] == [("user", "user"), ("default", "assistant")]
    assert history[-1]["id"] == message["id"]  # same id in stream and history
    assert client.get(f"/api/v1/chats/{chat}").json()["title"] == "hi"


def test_each_chat_has_its_own_agent_and_memory(client, provider):
    """Regression: the registry cached one agent per name, so all chats shared one memory."""
    first, second = _create(client), _create(client)
    provider.enqueue("one")
    provider.enqueue("two")

    _events(client.post(f"/api/v1/chats/{first}/messages", json={"prompt": "first chat"}))
    _events(client.post(f"/api/v1/chats/{second}/messages", json={"content": [{"type": "text", "text": "second chat"}]}))

    def user_prompts(chat):
        return [m["message"]["content"][0]["text"] for m in client.get(f"/api/v1/chats/{chat}/messages").json()
                if m["message"]["role"] == "user"]

    assert user_prompts(first) == ["first chat"]
    assert user_prompts(second) == ["second chat"]


def test_history_survives_runner_eviction(client, store, provider):
    chat = _create(client)
    provider.enqueue("remembered")
    _events(client.post(f"/api/v1/chats/{chat}/messages", json={"prompt": "hi"}))

    store._runners.clear()

    history = client.get(f"/api/v1/chats/{chat}/messages").json()
    assert [m["message"]["role"] for m in history] == ["user", "assistant"]
    # a new agent instance continues with the stored conversation
    provider.enqueue("again")
    _events(client.post(f"/api/v1/chats/{chat}/messages", json={"prompt": "next"}))
    assert [m.role for m in provider.requests[-1].messages][:2] == ["user", "assistant"]


def test_busy_chat_returns_409(client, store):
    chat = _create(client)
    store.runner(chat)._turn.acquire()  # a turn is running

    response = client.post(f"/api/v1/chats/{chat}/messages", json={"prompt": "hi"})

    assert response.status_code == 409


def test_agent_failure_streams_error_and_releases_turn(client, monkeypatch, provider):
    chat = _create(client)

    def boom(request, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(tasks_mod, "generate_chat_completion", boom)
    events = _events(client.post(f"/api/v1/chats/{chat}/messages", json={"prompt": "hi"}))
    assert any("provider down" in t for t in _texts(events))

    provider.enqueue("recovered")
    monkeypatch.setattr(tasks_mod, "generate_chat_completion",
                        lambda request, **kwargs: provider.generate_chat_completion(request))
    assert _texts(_events(client.post(f"/api/v1/chats/{chat}/messages", json={"prompt": "again"}))) == ["recovered"]


# -- tool approval (HITL) ------------------------------------------------------


def _start_tool_turn(store, provider, chat):
    provider.enqueue_tool_call("add", {"a": 2, "b": 3}, call_id="call-1")
    provider.enqueue("The answer is 5.")
    runner = store.runner(chat)
    return runner, runner.start("what is 2 + 3?")


def _next_message(events):
    for event in events:
        if isinstance(event, ChatMessageEvent):
            return event.message.message
    raise AssertionError("stream ended")


def test_tool_call_waits_for_approval_and_runs_when_allowed(client, store, provider, add_tool):
    chat = _create(client)
    runner, events = _start_tool_turn(store, provider, chat)

    request = _next_message(events)
    interaction = request.content[0]
    assert isinstance(interaction, UserInteractionContent) and interaction.interaction_id == "call-1"
    assert add_tool == []

    # the answer may arrive before or while the agent waits
    assert client.post(f"/api/v1/chats/{chat}/interactions/call-1", json={"choice": "Allow"}).status_code == 204

    result = _next_message(events).content[0]
    assert isinstance(result, ToolCallResultContent) and result.result == "5"
    assert add_tool == [(2, 3)]
    assert _next_message(events).content[0].text == "The answer is 5."
    list(events)
    assert not runner.busy

    # approval requests are not part of the model conversation
    history = client.get(f"/api/v1/chats/{chat}/messages").json()
    assert not any(p["type"] == "interaction" for m in history for p in m["message"]["content"])


def test_tool_call_denied(client, store, provider, add_tool):
    chat = _create(client)
    runner, events = _start_tool_turn(store, provider, chat)
    _next_message(events)

    # answered while the agent is waiting
    threading.Timer(0.1, lambda: runner.respond("call-1", "Deny")).start()
    result = _next_message(events).content[0]

    assert result.result == {"error": "Tool execution rejected."}
    assert add_tool == []
    list(events)


def test_interaction_endpoint_404s(client, store):
    chat = _create(client)
    assert client.post(f"/api/v1/chats/{chat}/interactions/x", json={"choice": "Allow"}).status_code == 404
    store.runner(chat)
    assert client.post(f"/api/v1/chats/{chat}/interactions/x", json={"choice": "Allow"}).status_code == 404


def test_cancel_rejects_pending_approval_and_ends_stream(client, store, provider, add_tool):
    chat = _create(client)
    runner, events = _start_tool_turn(store, provider, chat)
    _next_message(events)

    threading.Timer(0.1, lambda: client.post(f"/api/v1/chats/{chat}/cancel")).start()
    rest = list(events)

    assert add_tool == []
    assert not any(isinstance(e, ChatMessageEvent) for e in rest)
    assert not runner.busy
    assert runner.agent._tasks == type(runner.agent._tasks)()  # nothing left for the next turn


def _wait_until_idle(runner, timeout=5):
    deadline = time.monotonic() + timeout
    while runner.busy and time.monotonic() < deadline:
        time.sleep(0.01)
    return not runner.busy


def test_abandoned_stream_does_not_leave_chat_busy(client, store, provider, add_tool):
    """Regression: the turn was only released when the HTTP stream generator was resumed/closed,
    so a client that disconnected while waiting for an approval left the chat busy (409) forever."""
    chat = _create(client)
    runner, events = _start_tool_turn(store, provider, chat)
    _next_message(events)
    del events  # the client went away

    assert client.post(f"/api/v1/chats/{chat}/cancel").status_code == 204
    assert _wait_until_idle(runner)

    provider._responses.clear()  # the cancelled turn never used its queued answer
    provider.enqueue("still works")
    assert _texts(_events(client.post(f"/api/v1/chats/{chat}/messages", json={"prompt": "hi"}))) == ["still works"]


def test_abandoned_stream_is_released_after_approval_timeout(client, store, provider, add_tool):
    store.approval_timeout = 0.2
    chat = _create(client)
    runner, events = _start_tool_turn(store, provider, chat)
    _next_message(events)
    del events  # disconnected without cancelling

    assert _wait_until_idle(runner)
    assert add_tool == []


def test_unanswered_approval_times_out_in_stream(client, store, provider, add_tool):
    store.approval_timeout = 0.2
    chat = _create(client)
    provider.enqueue_tool_call("add", {"a": 1, "b": 1}, call_id="call-9")
    provider.enqueue("Ok.")

    events = _events(client.post(f"/api/v1/chats/{chat}/messages", json={"prompt": "add"}))

    types = [e["type"] if e["type"] != "message" else e["message"]["message"]["content"][0]["type"] for e in events]
    assert types[:3] == ["status", "interaction", "status"]
    assert {"type": "status", "status": "awaiting_input"} in events
    assert "tool_call_result" in types
    assert add_tool == []


# -- HITL controller -----------------------------------------------------------


def test_web_hitl_controller_wait_and_respond():
    hitl = WebHumanInTheLoopController(approval_timeout=5)
    assert not hitl.respond("c1", "Allow")  # not announced yet

    hitl.expect("c1")
    assert hitl.is_pending("c1")
    threading.Timer(0.05, lambda: hitl.respond("c1", "allow")).start()
    started = time.monotonic()
    assert hitl.request_tool_execution("t", {}, "c1") is True
    assert time.monotonic() - started < 2
    assert not hitl.is_pending("c1")
    assert not hitl.respond("c1", "Allow")  # already consumed


def test_web_hitl_controller_cancel_and_timeout():
    hitl = WebHumanInTheLoopController(approval_timeout=0.05)
    assert hitl.request_tool_execution("t", {}, "c1") is False  # timeout

    hitl.approval_timeout = 5
    threading.Timer(0.05, hitl.cancel).start()
    assert hitl.request_tool_execution("t", {}, "c2") is False
    assert hitl.request_tool_execution("t", {}, "c3") is False  # cancelled until reset

    hitl.reset()
    hitl.expect("c4")
    hitl.respond("c4", "Allow")
    assert hitl.request_tool_execution("t", {}, "c4") is True


def test_runner_start_is_exclusive(store):
    info = store.create("default")
    runner = store.runner(info.id)
    runner._turn.acquire()
    with pytest.raises(AgentBusyError):
        runner.start("hi")
