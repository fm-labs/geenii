"""The `geenii worker` click group (geenii.cli.worker_cli)."""

import json
from datetime import UTC, datetime

import pytest
from click.testing import CliRunner

import geenii.g
from geenii import worker
from geenii.agent.registry import AgentRegistry, AgentSpec
from geenii.cli.worker_cli import worker as worker_cli
from geenii.config import geenii_home
from geenii.ibc.comms import Blackboard, Mailbox


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    path = tmp_path / "geenii-home"
    monkeypatch.setenv("GEENII_HOME", str(path))
    monkeypatch.delenv("GEENII_APPROVE", raising=False)
    return path


@pytest.fixture(autouse=True)
def registry(monkeypatch):
    reg = AgentRegistry()
    reg.configs["bot"] = AgentSpec(name="bot", model="fake:test")
    monkeypatch.setattr(geenii.g, "get_agent_registry", lambda: reg)
    return reg


def run(*args, env=None):
    return CliRunner().invoke(worker_cli, list(args), env={"COLUMNS": "200", **(env or {})})


def test_help_lists_the_commands():
    result = run("--help")
    assert result.exit_code == 0
    for command in ("serve", "ask", "list", "inbox", "send", "blackboard", "post"):
        assert command in result.output


# -- mail ------------------------------------------------------------------------------


def test_send_and_read_inbox():
    result = run("send", "bot", "hello", "hi there")
    assert result.exit_code == 0, result.output
    (header,) = Mailbox("bot").list()
    assert result.output.strip() == f"Sent {header['id']} to bot."

    result = run("inbox", "bot")
    assert result.exit_code == 0 and f"{header['id']}" in result.output and "from human: hello" in result.output

    result = run("inbox", "bot", "--read", header["id"])
    assert result.exit_code == 0
    assert "From: human\nTo: bot" in result.output and "Subject: hello" in result.output
    assert result.output.rstrip().endswith("hi there")
    assert run("inbox", "bot").output.strip() == "No unread mail."
    assert "(read)" in run("inbox", "bot", "--all").output


def test_inbox_defaults_to_human_and_shows_reply_to():
    question = Mailbox.send("human", "bot", "q", "hi")
    answer = Mailbox.send("bot", "human", "Re: q", "the answer", reply_to=question["id"])
    assert answer["id"] in run("inbox").output
    assert f"In reply to: {question['id']}" in run("inbox", "--read", answer["id"]).output


def test_send_from_another_sender():
    assert run("send", "human", "s", "b", "--from", "bot").exit_code == 0
    assert Mailbox("human").list()[0]["from"] == "bot"


@pytest.mark.parametrize(
    ("args", "error"),
    [
        (("send", "nobody", "s", "b"), "Unknown agent 'nobody'"),
        (("send", "bot", "", "b"), "Subject must not be empty"),
        (("send", "bot", "s", "b", "--from", "Bad Name"), "Invalid agent name"),
        (("inbox", "bot", "--read", "000000000000"), "No message 000000000000"),
        (("inbox", "bot", "--read", "bad"), "Invalid message id"),
        (("post", "", "text"), "Topic must not be empty"),
    ],
)
def test_errors_exit_1_with_a_message(args, error):
    result = run(*args)
    assert result.exit_code == 1
    assert f"Error: {error}" in result.output
    assert "Traceback" not in result.output


# -- blackboard ----------------------------------------------------------------------


def test_post_and_blackboard():
    result = run("post", "news", "first")
    assert result.exit_code == 0 and result.output.startswith("Posted ") and "on news." in result.output
    run("post", "other", "second", "--as", "bot")

    output = run("blackboard").output
    assert "human on news:\nfirst" in output and "bot on other:\nsecond" in output
    assert "Topics: news (1), other (1)" in output

    output = run("blackboard", "--topic", "news", "-n", "5").output
    assert "first" in output and "second" not in output and "Topics:" not in output


def test_blackboard_new_only():
    assert run("blackboard", "--new").output.strip() == "No new entries."
    run("post", "news", "from bot", "--as", "bot")
    run("post", "news", "from me")
    output = run("blackboard", "--new").output
    assert "from bot" in output and "from me" not in output
    assert run("blackboard", "--new").output.strip() == "No new entries."


def test_send_to_a_channel():
    result = run("send", "@team", "plan", "let's go")
    assert result.exit_code == 0 and "to @team" in result.output
    assert run("send", "@Bad", "s", "b").exit_code != 0


def test_blackboard_empty():
    assert run("blackboard").output.strip() == "The blackboard is empty."
    assert Blackboard().read() == []


# -- workers -----------------------------------------------------------------------


def test_list_without_workers():
    assert run("list").output.strip() == "No workers running."


def test_list_shows_workers(home):
    folder = home / "workers" / "bot"
    folder.mkdir(parents=True)
    now = datetime.now(UTC).isoformat(timespec="seconds")
    (folder / "host-1.json").write_text(json.dumps({
        "agent": "bot", "instance": "host-1", "status": "busy", "busy_since": now, "handled": 7,
        "started": now, "last_seen": now,
    }))
    (folder / "host-2.json").write_text(json.dumps({
        "agent": "bot", "instance": "host-2", "status": "idle", "handled": 0,
        "started": "2026-01-01T00:00:00+00:00", "last_seen": "2026-01-01T00:00:00+00:00",
    }))
    output = run("list").output
    assert "host-1" in output and "busy" in output and "7" in output
    assert "host-2" in output and "gone?" in output


# -- serve and ask ---------------------------------------------------------------------


def test_serve_unknown_agent():
    result = run("serve", "nobody", "--once")
    assert result.exit_code == 1 and "Unknown agent 'nobody'" in result.output


def test_serve_passes_options(monkeypatch):
    calls = []
    monkeypatch.setattr(worker, "serve", lambda spec, **kw: calls.append((spec.name, kw)) or 0)

    assert run("serve", "bot", "--once", "-m", "fake:x", "--poll", "0.5", "--approve", "read").exit_code == 0
    assert run("serve", "bot", env={"GEENII_APPROVE": "all"}).exit_code == 0
    assert run("serve", "bot").exit_code == 0

    assert calls == [
        ("bot", {"model": "fake:x", "poll_seconds": 0.5, "once": True, "approval_policy": "read"}),
        ("bot", {"model": None, "poll_seconds": 2.0, "once": False, "approval_policy": "all"}),
        ("bot", {"model": None, "poll_seconds": 2.0, "once": False, "approval_policy": "none"}),
    ]


def test_serve_once_answers_the_inbox(monkeypatch):
    monkeypatch.setattr(worker, "handle", lambda spec, message, model, hitl: f"answer to {message['subject']}")
    run("send", "bot", "question", "hi")

    result = run("serve", "bot", "--once")

    assert result.exit_code == 0, result.output
    events = [json.loads(line)["event"] for line in result.output.splitlines() if line.startswith("{")]
    assert events == ["worker.start", "message.start", "message.done", "worker.stop"]
    (reply,) = [Mailbox("human").read(h["id"]) for h in Mailbox("human").list()]
    assert reply["body"] == "answer to question"


def test_ask_prints_the_reply(monkeypatch):
    monkeypatch.setattr(worker, "ask", lambda agent, text, sender, timeout: {"body": f"{agent} got '{text}' from {sender}"})
    result = run("ask", "bot", "what", "now?", "--from", "bot", "--timeout", "3")
    assert result.exit_code == 0 and result.output.strip() == "bot got 'what now?' from bot"


def test_ask_without_a_worker_times_out():
    result = run("ask", "bot", "anyone?", "--timeout", "0.05")
    assert result.exit_code == 1
    assert "No reply within 0.05s. Is 'geenii worker serve bot' running?" in result.output
    assert [h["subject"] for h in Mailbox("bot").list()] == ["anyone?"]


def test_ask_unknown_agent():
    result = run("ask", "nobody", "hi")
    assert result.exit_code == 1 and "Unknown agent 'nobody'" in result.output
    assert Mailbox("nobody").list() == []
