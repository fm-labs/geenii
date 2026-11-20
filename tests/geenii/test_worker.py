"""Workers (geenii.worker): answer selection, reply rules, the serve loop, heartbeat, recovery and ask."""

import json
import os
import socket
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest

import geenii.g
from geenii import worker
from geenii.agent import base_agent as base_agent_mod
from geenii.agent import tasks as tasks_mod
from geenii.agent.registry import AgentRegistry, AgentSpec
from geenii.chat_models import JsonContent, TextContent, ToolCallResultContent
from geenii.config import geenii_home
from geenii.datamodels import ModelMessage, SystemMessage
from geenii.hitl import PolicyHumanInTheLoopController
from geenii.ibc.comms import MAX_TEXT, Mailbox
from geenii.tool.registry import ToolRegistry


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    path = tmp_path / "geenii-home"
    monkeypatch.setenv("GEENII_HOME", str(path))
    return path


@pytest.fixture(autouse=True)
def registry(monkeypatch):
    reg = AgentRegistry()
    reg.configs["bot"] = AgentSpec(name="bot", model="fake:test")
    reg.configs["other"] = AgentSpec(name="other", model="fake:test")
    monkeypatch.setattr(geenii.g, "get_agent_registry", lambda: reg)
    return reg


@pytest.fixture
def spec(registry):
    return registry.get_config("bot")


@pytest.fixture
def answers(monkeypatch):
    """Replace the agent run: each message is answered with 'answer to <subject>'. Returns the handled messages."""
    handled = []

    def fake_handle(spec, message, model, hitl):
        handled.append(message)
        return f"answer to {message['subject']}"

    monkeypatch.setattr(worker, "handle", fake_handle)
    return handled


def _where(agent: str, message_id: str) -> str:
    mailbox = Mailbox(agent)
    return str(mailbox._find(message_id).parent.relative_to(mailbox.folder))


def _replies(agent: str = "human") -> list[dict]:
    mailbox = Mailbox(agent)
    return [mailbox.read(h["id"]) for h in mailbox.list()]


def _write_heartbeat(agent: str, instance: str, age_seconds: float) -> None:
    folder = geenii_home() / "workers" / agent
    folder.mkdir(parents=True, exist_ok=True)
    last_seen = (datetime.now(UTC) - timedelta(seconds=age_seconds)).isoformat(timespec="seconds")
    (folder / f"{instance}.json").write_text(json.dumps({"agent": agent, "instance": instance, "last_seen": last_seen}))


# -- final_answer --------------------------------------------------------------------


def _assistant(text):
    return ModelMessage(role="assistant", content=[TextContent(text=text)])


def _system(text, level):
    return SystemMessage(level=level, content=[TextContent(text=text)])


@pytest.mark.parametrize(
    ("messages", "expected"),
    [
        ([_assistant("the answer"), _system("compacted", "info")], "the answer"),
        ([_assistant("the answer"), _system("slow", "warning")], "the answer"),
        ([_assistant("partial"), _system("model crashed", "error")], "Error: model crashed"),
        ([_system("retrying", "error"), _assistant("the answer")], "the answer"),
        ([_assistant("the answer"), _system("", "error")], "the answer"),
        ([_system("note", "info")], "(no answer)"),
        ([ModelMessage(role="assistant", content=[JsonContent(data={"a": 1})])], '{\n  "a": 1\n}'),
        ([ModelMessage(role="user", content=[TextContent(text="question")])], "(no answer)"),
        ([], "(no answer)"),
    ],
)
def test_final_answer(messages, expected):
    assert worker.final_answer(messages) == expected


# -- reply rules ---------------------------------------------------------------------


def test_reply_answers_the_sender(spec):
    message = Mailbox.send("human", "bot", "question", "hi")
    assert worker.reply(spec, message, "the answer") is True
    (answer,) = _replies()
    assert answer["from"] == "bot" and answer["subject"] == "Re: question"
    assert answer["body"] == "the answer" and answer["reply_to"] == message["id"]


@pytest.mark.parametrize(
    ("sender", "reply_to"),
    [
        ("human", "aaaaaaaaaaaa"),  # a reply itself: never answered, so agents can't loop
        ("bot", None),  # from itself
        ("stranger", None),  # not a known agent
    ],
)
def test_reply_is_not_sent(spec, sender, reply_to):
    message = Mailbox.send(sender, "bot", "question", "hi", reply_to=reply_to)
    assert worker.reply(spec, message, "the answer") is False
    assert [r for r in _replies(sender) if r["reply_to"] == message["id"]] == []


def test_reply_fills_in_an_empty_answer_and_cuts_a_long_one(spec):
    message = Mailbox.send("human", "bot", "q", "hi")
    worker.reply(spec, message, "   ")
    worker.reply(spec, message, "x" * (MAX_TEXT + 500))
    empty, long = _replies()
    assert empty["body"] == "(no answer)"
    assert len(long["body"]) <= MAX_TEXT and long["body"].endswith("... [truncated]")


# -- approval policy -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("policy", "described", "allowed"),
    [
        ("none", "none", set()),
        ("", "none", set()),
        (None, "none", set()),
        ("all", "all", {"read", "bash"}),
        ("ALL", "all", {"read", "bash"}),
        ("read, web_fetch", "read,web_fetch", {"read"}),
    ],
)
def test_policy_controller(policy, described, allowed):
    controller = PolicyHumanInTheLoopController.from_policy(policy)
    assert controller.describe() == described
    assert {t for t in ("read", "bash") if controller.request_tool_execution(t, {}, "id")} == allowed


# -- handle, end to end with the fake model ----------------------------------------


@pytest.fixture
def fake_model(tmp_path, monkeypatch):
    """Route the agent's model calls to a FakeProvider; keep logs and plugins out of the test."""
    from geenii.provider.fake.provider import FakeProvider

    provider = FakeProvider()
    monkeypatch.setattr(tasks_mod, "generate_chat_completion",
                        lambda request, **kwargs: provider.generate_chat_completion(request))
    monkeypatch.setattr(base_agent_mod, "GEENII_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(geenii.g, "plugin_tools", ToolRegistry)
    return provider


@pytest.mark.parametrize(("policy", "tool_ran"), [("none", False), ("read", True)])
def test_handle_applies_the_approval_policy_to_tool_calls(tmp_path, fake_model, monkeypatch, policy, tool_ran):
    (tmp_path / "notes.txt").write_text("secret notes")
    spec = AgentSpec(name="bot", model="fake:test", tools=["read"], working_dir=str(tmp_path))
    fake_model.enqueue_tool_call("read", {"file_path": "notes.txt"})
    fake_model.enqueue("done")
    seen = []
    original = worker.final_answer
    monkeypatch.setattr(worker, "final_answer", lambda messages: (seen.extend(messages), original(messages))[1])

    message = Mailbox.send("human", "bot", "read it", "please read notes.txt")
    answer = worker.handle(spec, message, None, PolicyHumanInTheLoopController.from_policy(policy))

    assert answer == "done"
    results = [p for m in seen for p in m.content if isinstance(p, ToolCallResultContent)]
    assert len(results) == 1
    assert ("secret notes" in json.dumps(results[0].result)) is tool_ran
    user_texts = [m.to_text() for m in fake_model.requests[0].messages if m.role == "user"]
    assert user_texts[0] == "Message from agent 'human' (subject: read it):\n\nplease read notes.txt"


# -- serve ---------------------------------------------------------------------------


def test_serve_answers_each_message_and_acks_it(spec, answers, home):
    first = Mailbox.send("human", "bot", "one", "hi")
    second = Mailbox.send("other", "bot", "two", "hi")

    assert worker.serve(spec, once=True) == 0

    assert [m["id"] for m in answers] == [first["id"], second["id"]]
    assert [r["body"] for r in _replies("human")] == ["answer to one"]
    assert [r["body"] for r in _replies("other")] == ["answer to two"]
    assert _where("bot", first["id"]) == "read" and _where("bot", second["id"]) == "read"
    assert Mailbox("bot").owners() == []
    assert worker.list_workers() == []  # heartbeat removed on exit


def test_serve_passes_model_and_policy_to_handle(spec, monkeypatch):
    calls = []
    monkeypatch.setattr(worker, "handle", lambda s, m, model, hitl: calls.append((model, hitl.describe())) or "ok")
    Mailbox.send("human", "bot", "q", "hi")
    worker.serve(spec, model="fake:other", once=True, approval_policy="read")
    assert calls == [("fake:other", "read")]


def test_serve_replies_with_the_error_when_the_agent_fails(spec, monkeypatch):
    def broken(*args):
        raise RuntimeError("model unavailable")

    monkeypatch.setattr(worker, "handle", broken)
    message = Mailbox.send("human", "bot", "q", "hi")
    worker.serve(spec, once=True)
    (answer,) = _replies()
    assert answer["body"] == "Error while handling your message: model unavailable"
    assert _where("bot", message["id"]) == "read"


def test_serve_moves_a_message_to_failed_when_the_reply_cannot_be_sent(spec, answers, monkeypatch):
    message = Mailbox.send("human", "bot", "q", "hi")
    original_send = Mailbox.send

    def send(sender, to, *args, **kwargs):
        if sender == "bot":
            raise OSError("disk full")
        return original_send(sender, to, *args, **kwargs)

    monkeypatch.setattr(Mailbox, "send", staticmethod(send))
    worker.serve(spec, once=True)
    assert _where("bot", message["id"]) == "failed"


def test_serve_marks_a_busy_worker_in_its_heartbeat(spec, monkeypatch):
    states = []

    def slow(spec, message, model, hitl):
        (state,) = worker.list_workers()
        states.append(state)
        return "ok"

    monkeypatch.setattr(worker, "handle", slow)
    message = Mailbox.send("human", "bot", "q", "hi")
    worker.serve(spec, once=True)
    (state,) = states
    assert state["status"] == "busy" and state["message_id"] == message["id"] and state["alive"]
    assert state["instance"] == worker.instance_id() and state["handled"] == 0


# -- recovery -------------------------------------------------------------------------


def test_serve_recovers_messages_of_a_dead_worker_without_handling_them(spec, answers):
    message = Mailbox.send("human", "bot", "lost", "hi")
    Mailbox("bot").claim_next(owner="deadhost-1")  # claimed by a worker that has no heartbeat

    worker.serve(spec, once=True)

    assert answers == []  # never handled a second time
    assert _where("bot", message["id"]) == "failed"
    (notice,) = _replies()
    assert notice["reply_to"] == message["id"] and "could not be answered" in notice["body"]


def test_recovery_keeps_a_message_that_was_already_answered(spec, answers):
    message = Mailbox.send("human", "bot", "q", "hi")
    Mailbox("bot").claim_next(owner="deadhost-1")
    Mailbox.send("bot", "human", "Re: q", "the answer", reply_to=message["id"])  # died before ack

    worker.recover(spec, "me-1")

    assert _where("bot", message["id"]) == "read"
    assert [r["body"] for r in _replies()] == ["the answer"]  # no extra notice


def test_recovery_leaves_messages_of_live_workers_alone(spec):
    message = Mailbox.send("human", "bot", "q", "hi")
    Mailbox("bot").claim_next(owner="otherhost-1")
    _write_heartbeat("bot", "otherhost-1", age_seconds=5)

    assert worker.recover(spec, "me-1") == []
    assert _where("bot", message["id"]) == "processing/otherhost-1"


def test_recovery_at_startup_includes_messages_under_the_own_instance_id(spec):
    message = Mailbox.send("human", "bot", "q", "hi")
    Mailbox("bot").claim_next(owner="me-1")  # left by an earlier process with the same id

    assert worker.recover(spec, "me-1") == []  # a running worker's own messages are its own
    recovered = worker.recover(spec, "me-1", include_self=True)
    assert [m["id"] for _, m, _ in recovered] == [message["id"]]


def test_recovery_of_a_reply_does_not_notify(spec):
    message = Mailbox.send("other", "bot", "Re: x", "an answer", reply_to="aaaaaaaaaaaa")
    Mailbox("bot").claim_next(owner="deadhost-1")
    worker.recover(spec, "me-1")
    assert _where("bot", message["id"]) == "failed"
    assert _replies("other") == []


# -- instance_alive and list_workers ------------------------------------------------


def test_instance_alive_without_heartbeat_is_false():
    assert worker.instance_alive("bot", "otherhost-1") is False


def test_instance_alive_by_heartbeat_age():
    _write_heartbeat("bot", "otherhost-1", age_seconds=5)
    _write_heartbeat("bot", "otherhost-2", age_seconds=worker.STALE_SECONDS + 30)
    assert worker.instance_alive("bot", "otherhost-1") is True
    assert worker.instance_alive("bot", "otherhost-2") is False


def test_instance_alive_checks_the_pid_on_this_host():
    host = socket.gethostname()
    dead_pid = 2**22 + 12345  # above the usual pid range
    _write_heartbeat("bot", f"{host}-{os.getpid()}", age_seconds=1)
    _write_heartbeat("bot", f"{host}-{dead_pid}", age_seconds=1)
    assert worker.instance_alive("bot", f"{host}-{os.getpid()}") is True
    assert worker.instance_alive("bot", f"{host}-{dead_pid}") is False


def test_list_workers_marks_stale_ones_and_skips_damaged_files(home):
    _write_heartbeat("bot", "a-1", age_seconds=5)
    _write_heartbeat("bot", "b-1", age_seconds=worker.STALE_SECONDS + 30)
    folder = home / "workers" / "bot"
    (folder / "c-1.json").write_text("not json")
    (folder / "d-1.json").write_text("{}")
    (folder / "e-1.json").write_text('{"last_seen": "garbage"}')
    (folder / "f-1.json").write_text("[1]")
    workers = {w["instance"]: w["alive"] for w in worker.list_workers()}
    assert workers == {"a-1": True, "b-1": False}


# -- heartbeat ----------------------------------------------------------------------


def test_heartbeat_thread_keeps_beating_and_stops_on_remove():
    beats = []
    heartbeat = worker.Heartbeat("bot", "me-1", interval=0.02)
    original_beat = heartbeat.beat
    heartbeat.beat = lambda **changes: (beats.append(changes), original_beat(**changes))
    heartbeat.start()
    time.sleep(0.25)
    heartbeat.remove()
    count = len(beats)

    assert count >= 5  # the background thread beat on its own
    assert not heartbeat.path.exists()
    time.sleep(0.1)
    assert len(beats) == count  # stopped
    assert not heartbeat.path.exists()  # not written back


def test_heartbeat_file_content():
    heartbeat = worker.Heartbeat("bot", "me-1")
    heartbeat.beat(status="busy", message_id="abc")
    state = json.loads(heartbeat.path.read_text())
    assert state["agent"] == "bot" and state["instance"] == "me-1" and state["pid"] == os.getpid()
    assert state["status"] == "busy" and state["message_id"] == "abc" and state["handled"] == 0
    assert "last_seen" in state and "started" in state
    heartbeat.remove()


# -- ask -----------------------------------------------------------------------------


def test_ask_returns_the_reply_and_leaves_other_mail(spec):
    unrelated = Mailbox.send("other", "human", "hello", "unrelated")

    def answer_when_asked():
        mailbox = Mailbox("bot")
        for _ in range(100):
            message = mailbox.claim_next()
            if message:
                worker.reply(spec, message, "42")
                return
            time.sleep(0.01)

    thread = threading.Thread(target=answer_when_asked)
    thread.start()
    reply = worker.ask("bot", "What is the answer?\nThink hard.", timeout=5, poll_seconds=0.01)
    thread.join()

    assert reply["body"] == "42" and reply["subject"] == "Re: What is the answer?"
    assert [h["id"] for h in Mailbox("human").list()] == [unrelated["id"]]


def test_ask_times_out_and_leaves_the_message_in_the_inbox():
    assert worker.ask("bot", "anyone?", timeout=0.05, poll_seconds=0.01) is None
    assert [h["subject"] for h in Mailbox("bot").list()] == ["anyone?"]
