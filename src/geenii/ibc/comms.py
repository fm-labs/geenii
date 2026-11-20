"""How agents talk to each other: per-agent mail inboxes and group channels such as the blackboard.

Both are messages in one store (geenii.ibc.mailstore; the default is one SQLite database, GEENII_HOME/mail.db).
Mailbox.send checks names and texts and builds the message; the recipient decides where it goes.

Agent mail
    A recipient that is an agent name: the message goes to that agent's inbox. It is unread until it is
    read, which marks it read.

    A message can carry `attachments`: files of the file store (geenii.ibc.filestore), referenced by id. Sending
    shares them with the receiver, so they show in its filebox.

    A worker claims a message instead: it is processing (held by the worker) while the worker works on it,
    then read when it is done (ack) or failed when it couldn't answer it (fail). If the owner dies, recover()
    marks what it held failed, so a message is never handled twice.

Channels
    A recipient starting with '@' (CHANNEL_RE): the message is a post every agent and the human can read.
    Channels are open: anyone can post and read, and a channel exists once it has a post. Each agent has a
    cursor per channel, so Channel.read_new() returns only the posts it hasn't seen. Workers never handle
    posts.

    The blackboard is the channel '@blackboard'; Blackboard posts with the subject as topic.

"human" is a valid sender and receiver, so the user can take part through `geenii worker inbox` and
`geenii worker send`.
"""

from __future__ import annotations

import re
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from geenii.config import geenii_home
from geenii.ibc.mailstore import FAILED, PROCESSING, READ, UNREAD, MailboxStore, default_mailbox_store
from geenii.tool.python import PythonFunctionTool
from geenii.utils.schema import array, boolean, integer, params, string

try:
    import fcntl
except ImportError:  # Windows: no advisory locks; appends of one short line are still atomic in practice
    fcntl = None

HUMAN = "human"
MAX_TOPIC = 100
MAX_SUBJECT = 200
MAX_TEXT = 20_000
MAX_ATTACHMENTS = 20
_MESSAGE_ID_RE = re.compile(r"^[0-9a-f]{12}$")

AGENT_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
CHANNEL_RE = re.compile(r"^@[a-z0-9][a-z0-9_-]{0,63}$")
BLACKBOARD = "@blackboard"
# who holds a claimed message, e.g. a worker instance "<host>-<pid>"
OWNER_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$")


def check_agent_name(name: str) -> str:
    """Return the name if it is a valid agent name, else raise ValueError (names also become folder names)."""
    if not isinstance(name, str) or not AGENT_NAME_RE.fullmatch(name):
        raise ValueError(f"Invalid agent name {name!r}: use lowercase letters, digits, '-' and '_'")
    return name


def is_channel(name: str) -> bool:
    return isinstance(name, str) and name.startswith("@")


def check_channel_name(name: str) -> str:
    """Return the name if it is a valid channel name ('@' plus an agent-style name), else raise ValueError."""
    if not isinstance(name, str) or not CHANNEL_RE.fullmatch(name):
        raise ValueError(f"Invalid channel name {name!r}: use '@' and lowercase letters, digits, '-' and '_'")
    return name


def check_recipient(name: str) -> str:
    """An agent name or a channel name."""
    return check_channel_name(name) if is_channel(name) else check_agent_name(name)


def data_dir() -> Path:
    path = geenii_home() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _check_text(value: str, what: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} must not be empty")
    if len(value) > limit:
        raise ValueError(f"{what} is too long ({len(value)} characters, max {limit})")
    return value.strip()


@contextmanager
def _locked(file, exclusive: bool):
    if fcntl is not None:
        fcntl.flock(file, fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH)
    try:
        yield file
    finally:
        if fcntl is not None:
            fcntl.flock(file, fcntl.LOCK_UN)


# -- agent mail -----------------------------------------------------------------


class Mailbox:
    """The inbox of one agent. Checks names and texts and builds messages; a MailboxStore keeps them
    (default: SQLite, see geenii.ibc.mailstore)."""

    def __init__(self, agent: str, store: MailboxStore | None = None):
        self.agent = check_agent_name(agent)
        self.store = store or default_mailbox_store()

    @staticmethod
    def send(sender: str, to: str, subject: str, body: str, reply_to: str | None = None,
             attachments: list[str] | None = None, store: MailboxStore | None = None) -> dict:
        """Deliver a message to an agent's inbox, or post it if TO is a channel ('@name'). ATTACHMENTS are file
        store ids; each is shared with a receiving agent (files of channel posts are readable by id)."""
        message = {
            "id": _new_id(),
            "ts": _now().isoformat(timespec="seconds"),
            "from": check_agent_name(sender),
            "to": check_recipient(to),
            "subject": _check_text(subject, "Subject", MAX_SUBJECT),
            "body": _check_text(body, "Body", MAX_TEXT),
            "reply_to": reply_to or None,
        }
        if attachments:  # after the checks above, so a rejected message shares nothing
            message["attachments"] = _attach(attachments, to)
        store = store or default_mailbox_store()
        if is_channel(to):
            store.post(message)
        else:
            store.deliver(message)
        return message

    def list(self, include_read: bool = False, preview_chars: int = 0) -> list[dict]:
        """Headers of unread messages (and read and failed ones if asked), oldest first, optionally with a body
        preview."""
        states = (UNREAD, READ, FAILED) if include_read else (UNREAD,)
        headers = []
        for message, state, _owner in self.store.messages(self.agent, states):
            headers.append(
                {
                    "id": message.get("id"),
                    "ts": message.get("ts"),
                    "from": message.get("from"),
                    "subject": message.get("subject"),
                    "reply_to": message.get("reply_to"),
                    "read": state == READ,
                    "failed": state == FAILED,
                    "attachments": len(message.get("attachments") or []),
                }
            )
            if preview_chars:
                body = message.get("body") or ""
                headers[-1]["preview"] = body[:preview_chars] + ("..." if len(body) > preview_chars else "")
        return headers

    def _get(self, message_id: str) -> tuple[dict, str, str | None]:
        if not isinstance(message_id, str) or not _MESSAGE_ID_RE.fullmatch(message_id.strip()):
            raise ValueError(f"Invalid message id {message_id!r}")
        found = self.store.get(self.agent, message_id.strip())
        if found is None:
            raise ValueError(f"No message {message_id.strip()} in the inbox of {self.agent}")
        return found

    def status(self, message_id: str) -> tuple[str, str | None]:
        """(state, owner) of a message: unread, processing (with its owner), read or failed."""
        _message, state, owner = self._get(message_id)
        return state, owner

    def read(self, message_id: str) -> dict:
        """Return a message and mark it read if it was unread."""
        message, state, _owner = self._get(message_id)
        if state == UNREAD:
            self.store.mark_read(self.agent, message["id"])  # False only if someone took it first: still fine
        return message

    @staticmethod
    def _check_owner(owner: str) -> str:
        if not isinstance(owner, str) or not OWNER_RE.fullmatch(owner):
            raise ValueError(f"Invalid owner {owner!r}")
        return owner

    def claim_next(self, owner: str | None = None) -> dict | None:
        """Take the oldest unread message, or None if the inbox is empty. Safe with several readers.

        Without OWNER, the message is marked read at once. With OWNER, it is processing (held by OWNER)
        until ack() or fail() is called, or recover() finds that the owner is gone.
        """
        if owner is not None:
            self._check_owner(owner)
        return self.store.claim_next(self.agent, owner)

    def ack(self, message_id: str, owner: str) -> bool:
        """Mark a claimed message as done (read); False if OWNER doesn't hold it."""
        return self.store.finish(self.agent, message_id, self._check_owner(owner), READ)

    def fail(self, message_id: str, owner: str) -> bool:
        """Mark a claimed message as not answered (failed); False if OWNER doesn't hold it."""
        return self.store.finish(self.agent, message_id, self._check_owner(owner), FAILED)

    def owners(self) -> list[str]:
        """Owners that hold claimed messages."""
        return self.store.owners(self.agent)

    def recover(self, is_alive, was_answered=None) -> list[tuple[str, dict, bool]]:
        """Take the claimed messages of every owner for which `is_alive(owner)` is False.

        A message for which `was_answered(message)` is True (the owner died after replying) becomes read,
        every other one failed. They are never handed out again, so no message is handled twice.
        Returns (owner, message, answered) triples. Safe when several workers recover at once: each message
        is taken by one of them.
        """
        dead = {owner for owner in self.owners() if not is_alive(owner)}
        recovered = []
        for message, _state, owner in self.store.messages(self.agent, (PROCESSING,)):
            if owner not in dead:
                continue
            answered = bool(was_answered and was_answered(message))
            if self.store.finish(self.agent, message["id"], owner, READ if answered else FAILED):
                recovered.append((owner, message, answered))
        return recovered

    def find_reply(self, message_id: str) -> dict | None:
        """A message in this inbox that replies to MESSAGE_ID, if any."""
        return self.store.find_reply(self.agent, message_id)


# -- channels -------------------------------------------------------------------


class Channel:
    """A group channel ('@name'): posts that every agent and the human can read."""

    def __init__(self, name: str, store: MailboxStore | None = None):
        self.name = check_channel_name(name)
        self.store = store or default_mailbox_store()

    def post(self, sender: str, subject: str, body: str, reply_to: str | None = None,
             attachments: list[str] | None = None) -> dict:
        return Mailbox.send(sender, self.name, subject, body, reply_to=reply_to, attachments=attachments,
                            store=self.store)

    def read(self, topic: str | None = None, limit: int = 20, author: str | None = None) -> list[dict]:
        """The latest `limit` posts, oldest first, optionally only for one subject (case-insensitive) or author.
        Doesn't move anyone's cursor."""
        return [m for _, m in self.store.channel_messages(self.name, subject=topic or None, sender=author or None,
                                                          limit=limit)]

    def read_new(self, agent: str, limit: int = 20) -> list[dict]:
        """Posts AGENT hasn't seen yet (up to `limit`, oldest first; the rest come with the next call), without
        AGENT's own posts. Moves AGENT's cursor past what it returns. The first call returns nothing and starts
        the cursor at the newest post; use read() for older posts."""
        check_agent_name(agent)
        cursor = self.store.get_cursor(self.name, agent)
        if cursor is None:
            self.store.advance_cursor(self.name, agent, self.store.channel_end(self.name))
            return []
        posts = self.store.channel_messages(self.name, after=cursor, limit=limit)
        if posts:
            self.store.advance_cursor(self.name, agent, posts[-1][0])
        return [m for _, m in posts if m.get("from") != agent]

    def topics(self) -> dict[str, int]:
        """Number of posts per subject, in order of first use."""
        return self.store.subjects(self.name)


class Blackboard(Channel):
    """The shared blackboard: the channel '@blackboard', with the subject as topic."""

    def __init__(self, store: MailboxStore | None = None):
        super().__init__(BLACKBOARD, store)

    def post(self, author: str, topic: str, text: str, reply_to: str | None = None,
             attachments: list[str] | None = None) -> dict:
        return super().post(author, _check_text(topic, "Topic", MAX_TOPIC), text, reply_to=reply_to,
                            attachments=attachments)


def _attach(file_ids: list[str], to: str) -> list[dict]:
    """Check the file ids, share the files with TO (unless it is a channel) and return the attachment entries
    {id, name, size, mime}."""
    from geenii.ibc.filestore import FileStore  # lazy: files imports this module

    if isinstance(file_ids, str):
        file_ids = [file_ids]
    file_ids = list(dict.fromkeys(f.strip() for f in file_ids if isinstance(f, str) and f.strip()))
    if len(file_ids) > MAX_ATTACHMENTS:
        raise ValueError(f"Too many attachments ({len(file_ids)}, max {MAX_ATTACHMENTS})")
    store = FileStore()
    metas = [store.info(file_id) for file_id in file_ids]  # all must exist before anything is shared
    if not is_channel(check_recipient(to)):
        metas = [store.share(m["id"], [to]) for m in metas]
    return [{k: meta[k] for k in ("id", "name", "size", "mime")} for meta in metas]


# -- text formatting for slash commands and the CLI ----------------------------


def format_inbox(headers: list[dict]) -> str:
    if not headers:
        return "No unread mail."
    return "\n".join(
        f"{h['id']}  {h['ts']}  from {h['from']}: {h['subject']}"
        + ("  (read)" if h.get("read") else "")
        + ("  (failed)" if h.get("failed") else "")
        + (f"  [{h['attachments']} file{'s' if h['attachments'] != 1 else ''}]" if h.get("attachments") else "")
        for h in headers
    )


def format_blackboard(entries: list[dict]) -> str:
    if not entries:
        return "The blackboard is empty."
    return "\n\n".join(f"[{e['ts']}] {e['from']} on {e['subject']}:\n{e['body']}" for e in entries)


# -- tools bound to one agent ---------------------------------------------------


def known_agents() -> dict[str, str]:
    """Agent name -> description, including the human."""
    from geenii.g import get_agent_registry  # lazy: geenii.g is heavy to import

    agents = {name: spec.description or "" for name, spec in get_agent_registry().configs.items()}
    agents[HUMAN] = "The human user"
    return agents


# name -> (description, parameters) of the comms tools; shared by comms_tools() and the stubs in ibc/tools.py
COMMS_TOOL_DEFS: dict[str, tuple[str, dict]] = {
    "blackboard_post": (
        "Post a note to the shared blackboard that all agents and the human can read.",
        params(
            topic=string("Short topic, e.g. 'monthly-report'. Use the same topic for related notes."),
            text=string("The note"),
            required=["topic", "text"],
        ),
    ),
    "blackboard_read": (
        "Read the latest blackboard entries, optionally for one topic, or with new_only the entries posted since "
        "you last checked. With no entries it lists the topics.",
        params(
            topic=string("Only entries with this topic (empty for all; ignored with new_only)"),
            limit=integer("Maximum number of entries, default 20"),
            new_only=boolean("Only entries you haven't seen yet, without your own; default false"),
        ),
    ),
    "agentmail_send": (
        "Send a direct message to another agent's inbox (or to 'human'), or post it to a channel ('@name').",
        params(
            to=string("Receiver agent name (see agentmail_contacts) or channel ('@name')"),
            subject=string("Subject line"),
            body=string("Message text"),
            reply_to=string("Id of the message this replies to, if any"),
            attachments=array(string("File id"), "Ids of stored files to attach (see filestore_upload)"),
            required=["to", "subject", "body"],
        ),
    ),
    "agentmail_check_inbox": (
        "Fetch your new agent mail (full messages). Fetched messages are marked read.",
        params(),
    ),
    "agentmail_read": (
        "Open a message by id again, including ones already fetched.",
        params(message_id=string("Message id from agentmail_check_inbox"), required=["message_id"]),
    ),
    "agentmail_contacts": (
        "List the other agents you can send mail to.",
        params(),
    ),
}

COMMS_TOOL_NAMES = frozenset(COMMS_TOOL_DEFS)


def comms_tools(agent_name: str):
    """The blackboard and mail tools for one agent. The sender is always `agent_name`."""

    check_agent_name(agent_name)
    board = Blackboard()
    mailbox = Mailbox(agent_name)

    def blackboard_post(topic: str, text: str) -> dict:
        return board.post(agent_name, topic, text)

    def blackboard_read(topic: str = "", limit: int = 20, new_only: bool = False) -> dict:
        if new_only:
            entries = board.read_new(agent_name, limit=limit)
            return {"entries": entries} if entries else {"entries": [], "note": "No new entries.",
                                                         "topics": board.topics()}
        entries = board.read(topic=topic or None, limit=limit)
        return {"entries": entries} if entries else {"entries": [], "topics": board.topics()}

    def agentmail_send(to: str, subject: str, body: str, reply_to: str = "", attachments: list[str] | None = None) -> dict:
        to = to.strip().lower()
        if to == agent_name:
            raise ValueError("You can't send mail to yourself")
        if not is_channel(to) and to not in known_agents():
            raise ValueError(f"Unknown agent {to!r}. Known: {', '.join(sorted(known_agents()))}")
        message = Mailbox.send(agent_name, to, subject, body, reply_to=reply_to or None, attachments=attachments)
        result = {"sent": True, "id": message["id"], "to": to}
        if message.get("attachments"):
            result["attachments"] = [a["id"] for a in message["attachments"]]
        return result

    def agentmail_check_inbox() -> dict:
        # deliver unread mail in full and mark it read, so the same message is never handled twice
        messages = [mailbox.read(h["id"]) for h in mailbox.list()]
        if not messages:
            return {"new_messages": [], "note": "No new mail."}
        return {"new_messages": messages}

    def agentmail_read(message_id: str) -> dict:
        return mailbox.read(message_id)

    def agentmail_contacts() -> dict:
        return {name: desc for name, desc in known_agents().items() if name != agent_name}

    handlers = {
        "blackboard_post": blackboard_post,
        "blackboard_read": blackboard_read,
        "agentmail_send": agentmail_send,
        "agentmail_check_inbox": agentmail_check_inbox,
        "agentmail_read": agentmail_read,
        "agentmail_contacts": agentmail_contacts,
    }
    return [
        PythonFunctionTool(name, description, parameters, handlers[name])
        for name, (description, parameters) in COMMS_TOOL_DEFS.items()
    ]
