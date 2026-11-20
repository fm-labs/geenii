"""Agent mail and the blackboard (geenii.ibc.comms): file layout, validation, claims/leases and recovery."""

import json
import threading

import pytest

import geenii.g
from geenii import config
from geenii.agent.registry import AgentRegistry, AgentSpec
from geenii.ibc import comms
from geenii.ibc.comms import MAX_SUBJECT, MAX_TEXT, Blackboard, Mailbox, format_inbox, known_agents


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    """GEENII_HOME in a temp dir."""
    path = tmp_path / "geenii-home"
    monkeypatch.setenv("GEENII_HOME", str(path))
    return path


@pytest.fixture(autouse=True)
def registry(monkeypatch):
    """A small global agent registry: 'bot' and 'other'."""
    reg = AgentRegistry()
    reg.configs["bot"] = AgentSpec(name="bot", description="The bot")
    reg.configs["other"] = AgentSpec(name="other", description="Another bot")
    monkeypatch.setattr(geenii.g, "get_agent_registry", lambda: reg)
    return reg


def _send(subject="hello", body="hi", sender="human", to="bot", reply_to=None):
    return Mailbox.send(sender, to, subject, body, reply_to=reply_to)


def _where(mailbox: Mailbox, message_id: str) -> str:
    """The folder a message is in, relative to the inbox ('.' for unread)."""
    return str(mailbox._find(message_id).parent.relative_to(mailbox.folder))


# -- geenii_home ----------------------------------------------------------------


def test_geenii_home_uses_env_var(home):
    assert config.geenii_home() == home
    assert home.is_dir()


def test_geenii_home_defaults_to_dot_geenii_in_user_home(tmp_path, monkeypatch):
    monkeypatch.delenv("GEENII_HOME")
    monkeypatch.setattr(config, "GEENII_USER_HOME", str(tmp_path / "user"))
    assert config.geenii_home() == tmp_path / "user" / ".geenii"


# -- sending and reading -----------------------------------------------------------


def test_send_writes_one_json_file_into_the_receivers_inbox(home):
    message = _send(subject=" hello ", body=" hi ")
    files = list((home / "inbox" / "bot").glob("*.json"))
    assert len(files) == 1
    assert files[0].name.endswith(f"-{message['id']}.json")
    assert json.loads(files[0].read_text()) == message
    assert message["subject"] == "hello" and message["body"] == "hi"  # stripped
    assert message["from"] == "human" and message["to"] == "bot" and message["reply_to"] is None
    assert not list((home / "inbox" / "bot").glob(".*"))  # no temp file left


def test_list_returns_unread_headers_oldest_first():
    first, second = _send("one"), _send("two")
    headers = Mailbox("bot").list()
    assert [h["id"] for h in headers] == [first["id"], second["id"]]
    assert headers[0] == {
        "id": first["id"], "ts": first["ts"], "from": "human", "subject": "one", "reply_to": None,
        "read": False, "failed": False, "attachments": 0,
    }


def test_list_preview():
    _send(body="x" * 30)
    (header,) = Mailbox("bot").list(preview_chars=10)
    assert header["preview"] == "x" * 10 + "..."


def test_read_moves_message_to_read_folder():
    message = _send()
    mailbox = Mailbox("bot")
    assert mailbox.read(message["id"]) == message
    assert mailbox.list() == []
    assert _where(mailbox, message["id"]) == "read"
    assert [h["read"] for h in mailbox.list(include_read=True)] == [True]
    assert mailbox.read(message["id"]) == message  # reading again works


def test_read_rejects_invalid_and_unknown_ids():
    mailbox = Mailbox("bot")
    with pytest.raises(ValueError, match="Invalid message id"):
        mailbox.read("../../etc")
    with pytest.raises(ValueError, match="No message"):
        mailbox.read("000000000000")


@pytest.mark.parametrize(
    ("kwargs", "error"),
    [
        ({"sender": "Bad Name"}, "Invalid agent name"),
        ({"to": "../escape"}, "Invalid agent name"),
        ({"subject": "  "}, "Subject must not be empty"),
        ({"subject": "s" * (MAX_SUBJECT + 1)}, "Subject is too long"),
        ({"body": ""}, "Body must not be empty"),
        ({"body": "b" * (MAX_TEXT + 1)}, "Body is too long"),
    ],
)
def test_send_validates(kwargs, error):
    with pytest.raises(ValueError, match=error):
        _send(**kwargs)


def test_find_reply():
    question = _send(sender="other", to="bot")
    assert Mailbox("other").find_reply(question["id"]) is None
    answer = _send(sender="bot", to="other", subject="Re: hello", reply_to=question["id"])
    assert Mailbox("other").find_reply(question["id"]) == answer
    Mailbox("other").read(answer["id"])
    assert Mailbox("other").find_reply(question["id"]) == answer  # also when read


def test_format_inbox():
    assert format_inbox([]) == "No unread mail."
    message = _send()
    line = format_inbox(Mailbox("bot").list())
    assert message["id"] in line and "from human: hello" in line and "(read)" not in line


# -- claims, leases and recovery ---------------------------------------------------


def test_claim_without_owner_marks_read():
    message = _send()
    mailbox = Mailbox("bot")
    assert mailbox.claim_next() == message
    assert _where(mailbox, message["id"]) == "read"
    assert mailbox.claim_next() is None


def test_claim_with_owner_leases_oldest_message_until_ack():
    first, second = _send("one"), _send("two")
    mailbox = Mailbox("bot")
    assert mailbox.claim_next(owner="host-1") == first
    assert _where(mailbox, first["id"]) == "processing/host-1"
    assert mailbox.owners() == ["host-1"]
    assert [h["id"] for h in mailbox.list()] == [second["id"]]  # not offered again

    assert mailbox.ack(first["id"], "host-1") is True
    assert _where(mailbox, first["id"]) == "read"
    assert mailbox.owners() == []


def test_fail_moves_to_failed_and_list_shows_it():
    message = _send()
    mailbox = Mailbox("bot")
    mailbox.claim_next(owner="host-1")
    assert mailbox.fail(message["id"], "host-1") is True
    assert _where(mailbox, message["id"]) == "failed"
    assert mailbox.list() == []
    (header,) = mailbox.list(include_read=True)
    assert header["failed"] is True and header["read"] is False
    assert "(failed)" in format_inbox([header])


def test_ack_and_fail_only_work_for_the_owner():
    message = _send()
    mailbox = Mailbox("bot")
    mailbox.claim_next(owner="host-1")
    assert mailbox.ack(message["id"], "host-2") is False
    assert mailbox.fail(message["id"], "host-2") is False
    assert _where(mailbox, message["id"]) == "processing/host-1"


@pytest.mark.parametrize("owner", ["", ".hidden", "a/b", "../x", "x" * 129])
def test_invalid_owner_is_rejected(owner):
    _send()
    with pytest.raises(ValueError, match="Invalid owner"):
        Mailbox("bot").claim_next(owner=owner)


def test_read_finds_a_claimed_message_without_moving_it():
    message = _send()
    mailbox = Mailbox("bot")
    mailbox.claim_next(owner="host-1")
    assert mailbox.read(message["id"]) == message
    assert _where(mailbox, message["id"]) == "processing/host-1"


def test_concurrent_claims_hand_out_each_message_once():
    sent = {_send(f"m{i}")["id"] for i in range(60)}
    claimed: list[str] = []
    lock = threading.Lock()

    def work(owner):
        mailbox = Mailbox("bot")
        while (message := mailbox.claim_next(owner=owner)) is not None:
            with lock:
                claimed.append(message["id"])

    threads = [threading.Thread(target=work, args=(f"host-{i}",)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(claimed) == sorted(sent)


def test_recover_moves_messages_of_dead_owners_only():
    dead, alive = _send("dead"), _send("alive")
    mailbox = Mailbox("bot")
    mailbox.claim_next(owner="dead-1")
    mailbox.claim_next(owner="alive-1")

    recovered = mailbox.recover(lambda owner: owner == "alive-1")

    assert recovered == [("dead-1", dead, False)]
    assert _where(mailbox, dead["id"]) == "failed"
    assert _where(mailbox, alive["id"]) == "processing/alive-1"
    assert mailbox.list() == []  # never put back into the inbox


def test_recover_moves_answered_messages_to_read():
    answered, unanswered = _send("answered"), _send("unanswered")
    mailbox = Mailbox("bot")
    mailbox.claim_next(owner="dead-1")
    mailbox.claim_next(owner="dead-1")

    recovered = mailbox.recover(lambda owner: False, lambda m: m["id"] == answered["id"])

    assert sorted((m["id"], a) for _, m, a in recovered) == sorted(
        [(answered["id"], True), (unanswered["id"], False)]
    )
    assert _where(mailbox, answered["id"]) == "read"
    assert _where(mailbox, unanswered["id"]) == "failed"


# -- blackboard --------------------------------------------------------------------


def test_blackboard_post_and_read(home):
    board = Blackboard()
    entry = board.post("human", " News ", " first ")
    assert entry["topic"] == "News" and entry["text"] == "first" and entry["author"] == "human"
    assert board.path == home / "blackboard.jsonl"
    assert board.read() == [entry]


def test_blackboard_filters_and_limit():
    board = Blackboard()
    board.post("human", "news", "one")
    board.post("bot", "News", "two")
    board.post("bot", "other", "three")
    assert [e["text"] for e in board.read(topic="NEWS")] == ["one", "two"]
    assert [e["text"] for e in board.read(author="bot")] == ["two", "three"]
    assert [e["text"] for e in board.read(limit=2)] == ["two", "three"]
    assert board.topics() == {"news": 1, "News": 1, "other": 1}


def test_blackboard_skips_damaged_lines(home):
    board = Blackboard()
    board.post("human", "t", "good")
    with open(board.path, "a", encoding="utf-8") as f:
        f.write("not json\n")
    board.post("human", "t", "also good")
    assert [e["text"] for e in board.read()] == ["good", "also good"]


def test_blackboard_validates():
    board = Blackboard()
    with pytest.raises(ValueError):
        board.post("Not Valid", "t", "x")
    with pytest.raises(ValueError):
        board.post("human", "", "x")
    with pytest.raises(ValueError):
        board.post("human", "t", "x" * (MAX_TEXT + 1))
    assert board.read() == []


# -- known agents and agent tools --------------------------------------------------


def test_known_agents_are_the_registry_plus_human():
    assert known_agents() == {"bot": "The bot", "other": "Another bot", "human": "The human user"}


def _tools(agent):
    return {t.name: t for t in comms.comms_tools(agent)}


def _call(tool, **args):
    return tool.handler(**args)


def test_send_mail_tool_checks_receiver():
    tools = _tools("bot")
    with pytest.raises(ValueError, match="yourself"):
        _call(tools["send_mail"], to="bot", subject="s", body="b")
    with pytest.raises(ValueError, match="Unknown agent"):
        _call(tools["send_mail"], to="nobody", subject="s", body="b")
    result = _call(tools["send_mail"], to=" Other ", subject="s", body="b")
    assert result["sent"] and result["to"] == "other"
    assert Mailbox("other").list()[0]["from"] == "bot"


def test_check_inbox_tool_returns_full_messages_and_marks_them_read():
    message = _send()
    tools = _tools("bot")
    assert _call(tools["check_inbox"]) == {"new_messages": [message]}
    assert _call(tools["check_inbox"])["new_messages"] == []
    assert _call(tools["read_mail"], message_id=message["id"]) == message


def test_list_agents_tool_excludes_self():
    assert set(_call(_tools("bot")["list_agents"])) == {"other", "human"}


def test_blackboard_tools_post_as_the_agent():
    tools = _tools("bot")
    _call(tools["blackboard_post"], topic="t", text="x")
    assert _call(tools["blackboard_read"])["entries"][0]["author"] == "bot"
    assert _call(tools["blackboard_read"], topic="none") == {"entries": [], "topics": {"t": 1}}
