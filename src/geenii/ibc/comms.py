"""How agents talk to each other: a shared blackboard and per-agent mail inboxes.

Blackboard
    One append-only JSONL file (GEENII_HOME/blackboard.jsonl). Every agent and the human can post an
    entry under a topic and read the latest entries. Writes hold an exclusive file lock, so agents running
    in parallel never interleave lines.

Agent mail
    One folder per agent (GEENII_HOME/inbox/<agent>/). A message is one JSON file. The sender writes it to a
    hidden temp file inside the receiver's inbox and renames it into place, so the receiver never sees a
    half-written message. Reading a message moves it to inbox/<agent>/read/.

    A message can carry `attachments`: files of the file store (geenii.ibc.files), referenced by id. Sending
    shares them with the receiver, so they show in its filebox.

    A worker claims a message instead: it moves it to processing/<owner>/ while it works on it, then to
    read/ when it is done (ack) or to failed/ when it couldn't answer it (fail). If the owner dies, recover()
    moves what it held to failed/, so a message is never handled twice.

"human" is a valid sender and receiver, so the user can take part through `geenii worker inbox` and
`geenii worker send`.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from geenii.config import geenii_home
from geenii.tool.python import PythonFunctionTool
from geenii.utils.schema import array, integer, params, string

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
# who holds a claimed message, e.g. a worker instance "<host>-<pid>"; becomes a folder name
OWNER_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$")


def check_agent_name(name: str) -> str:
    """Return the name if it is a valid agent name, else raise ValueError (names become folder names)."""
    if not isinstance(name, str) or not AGENT_NAME_RE.fullmatch(name):
        raise ValueError(f"Invalid agent name {name!r}: use lowercase letters, digits, '-' and '_'")
    return name


def data_dir() -> Path:
    path = geenii_home() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def blackboard_file() -> Path:
    return geenii_home() / "blackboard.jsonl"


def inbox_dir(agent: str) -> Path:
    return geenii_home() / "inbox" / check_agent_name(agent)


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


# -- blackboard -----------------------------------------------------------------


class Blackboard:
    def __init__(self, path: Path | None = None):
        self._path = path

    @property
    def path(self) -> Path:
        return self._path or blackboard_file()

    def post(self, author: str, topic: str, text: str) -> dict:
        entry = {
            "id": _new_id(),
            "ts": _now().isoformat(timespec="seconds"),
            "author": check_agent_name(author),
            "topic": _check_text(topic, "Topic", MAX_TOPIC),
            "text": _check_text(text, "Text", MAX_TEXT),
        }
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with open(self.path, "a", encoding="utf-8") as f, _locked(f, exclusive=True):
            f.write(line)
            f.flush()
        return entry

    def read(self, topic: str | None = None, limit: int = 20, author: str | None = None) -> list[dict]:
        """The latest `limit` entries, oldest first, optionally only for one topic (case-insensitive) or author."""
        if not self.path.exists():
            return []
        with open(self.path, encoding="utf-8") as f, _locked(f, exclusive=False):
            lines = f.readlines()
        entries = []
        for line in lines:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue  # skip a damaged line rather than losing the whole board
            if topic and entry.get("topic", "").lower() != topic.strip().lower():
                continue
            if author and entry.get("author") != author:
                continue
            entries.append(entry)
        return entries[-max(1, int(limit)) :]

    def topics(self) -> dict[str, int]:
        """Number of entries per topic."""
        counts: dict[str, int] = {}
        for entry in self.read(limit=10**9):
            counts[entry["topic"]] = counts.get(entry["topic"], 0) + 1
        return counts


# -- agent mail -----------------------------------------------------------------


class Mailbox:
    """The inbox of one agent."""

    def __init__(self, agent: str):
        self.agent = check_agent_name(agent)

    @property
    def folder(self) -> Path:
        return inbox_dir(self.agent)

    @staticmethod
    def send(sender: str, to: str, subject: str, body: str, reply_to: str | None = None,
             attachments: list[str] | None = None) -> dict:
        """Deliver a message. ATTACHMENTS are file store ids; each is shared with the receiver."""
        now = _now()
        message = {
            "id": _new_id(),
            "ts": now.isoformat(timespec="seconds"),
            "from": check_agent_name(sender),
            "to": check_agent_name(to),
            "subject": _check_text(subject, "Subject", MAX_SUBJECT),
            "body": _check_text(body, "Body", MAX_TEXT),
            "reply_to": reply_to or None,
        }
        if attachments:  # after the checks above, so a rejected message shares nothing
            message["attachments"] = _attach(attachments, to)
        folder = inbox_dir(to)
        folder.mkdir(parents=True, exist_ok=True)
        name = f"{now.strftime('%Y%m%dT%H%M%S%fZ')}-{message['id']}.json"
        tmp = folder / f".{name}.tmp"
        tmp.write_text(json.dumps(message, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, folder / name)  # atomic: the receiver sees the whole message or nothing
        return message

    def _files(self, folder: Path) -> list[Path]:
        if not folder.is_dir():
            return []
        return sorted(p for p in folder.glob("*.json") if not p.name.startswith("."))

    @property
    def processing_folder(self) -> Path:
        return self.folder / "processing"

    @property
    def failed_folder(self) -> Path:
        return self.folder / "failed"

    def list(self, include_read: bool = False, preview_chars: int = 0) -> list[dict]:
        """Headers of unread messages (and read and failed ones if asked), oldest first, optionally with a body
        preview."""
        files = self._files(self.folder)
        if include_read:
            files += self._files(self.folder / "read") + self._files(self.failed_folder)
        headers = []
        for path in files:
            try:
                message = json.loads(path.read_text(encoding="utf-8"))
            except OSError, json.JSONDecodeError:
                continue
            headers.append(
                {
                    "id": message.get("id"),
                    "ts": message.get("ts"),
                    "from": message.get("from"),
                    "subject": message.get("subject"),
                    "reply_to": message.get("reply_to"),
                    "read": path.parent.name == "read",
                    "failed": path.parent.name == "failed",
                    "attachments": len(message.get("attachments") or []),
                }
            )
            if preview_chars:
                body = message.get("body") or ""
                headers[-1]["preview"] = body[:preview_chars] + ("..." if len(body) > preview_chars else "")
        return headers

    def _find(self, message_id: str) -> Path:
        if not isinstance(message_id, str) or not _MESSAGE_ID_RE.fullmatch(message_id.strip()):
            raise ValueError(f"Invalid message id {message_id!r}")
        message_id = message_id.strip()
        folders = [self.folder, self.folder / "read", self.failed_folder]
        if self.processing_folder.is_dir():
            folders += sorted(p for p in self.processing_folder.iterdir() if p.is_dir())
        for folder in folders:
            matches = list(folder.glob(f"*-{message_id}.json")) if folder.is_dir() else []
            if matches:
                return matches[0]
        raise ValueError(f"No message {message_id} in the inbox of {self.agent}")

    def _take(self, path: Path, folder: Path | None = None) -> dict | None:
        """Move a message to FOLDER (default read/) and return it; None if another reader moved it first.

        The rename is atomic, so when several instances of an agent share one inbox, exactly one of them
        gets each message.
        """
        folder = folder or self.folder / "read"
        folder.mkdir(parents=True, exist_ok=True)
        target = folder / path.name
        try:
            os.replace(path, target)
        except FileNotFoundError:
            return None
        return json.loads(target.read_text(encoding="utf-8"))

    def read(self, message_id: str) -> dict:
        """Return a message and move it to the read/ folder."""
        path = self._find(message_id)
        if path.parent == self.folder:
            message = self._take(path)
            if message is None:
                return json.loads(self._find(message_id).read_text(encoding="utf-8"))
            return message
        return json.loads(path.read_text(encoding="utf-8"))

    def _owner_folder(self, owner: str) -> Path:
        if not isinstance(owner, str) or not OWNER_RE.fullmatch(owner):
            raise ValueError(f"Invalid owner {owner!r}")
        return self.processing_folder / owner

    def claim_next(self, owner: str | None = None) -> dict | None:
        """Take the oldest unread message, or None if the inbox is empty. Safe with several readers.

        Without OWNER, the message is marked read at once. With OWNER, it moves to processing/<owner>/
        until ack() or fail() is called, or recover() finds that the owner is gone.
        """
        folder = self._owner_folder(owner) if owner is not None else None
        for path in self._files(self.folder):
            message = self._take(path, folder)
            if message is not None:
                return message
        return None

    def _finish(self, message_id: str, owner: str, folder: Path) -> bool:
        matches = list(self._owner_folder(owner).glob(f"*-{message_id}.json"))
        return bool(matches) and self._take(matches[0], folder) is not None

    def ack(self, message_id: str, owner: str) -> bool:
        """Mark a claimed message as done (move it to read/); False if OWNER doesn't hold it."""
        return self._finish(message_id, owner, self.folder / "read")

    def fail(self, message_id: str, owner: str) -> bool:
        """Mark a claimed message as not answered (move it to failed/); False if OWNER doesn't hold it."""
        return self._finish(message_id, owner, self.failed_folder)

    def owners(self) -> list[str]:
        """Owners that hold claimed messages."""
        if not self.processing_folder.is_dir():
            return []
        return sorted(p.name for p in self.processing_folder.iterdir() if p.is_dir() and self._files(p))

    def recover(self, is_alive, was_answered=None) -> list[tuple[str, dict, bool]]:
        """Take the claimed messages of every owner for which `is_alive(owner)` is False.

        A message for which `was_answered(message)` is True (the owner died after replying) moves to read/,
        every other one to failed/. They are never handed out again, so no message is handled twice.
        Returns (owner, message, answered) triples. Safe when several workers recover at once: each message
        is moved by one of them.
        """
        recovered = []
        for owner in self.owners():
            if is_alive(owner):
                continue
            for path in self._files(self.processing_folder / owner):
                try:
                    message = json.loads(path.read_text(encoding="utf-8"))
                except FileNotFoundError:
                    continue  # another worker recovered it first
                except (OSError, json.JSONDecodeError):
                    message = None
                answered = bool(message and was_answered and was_answered(message))
                taken = self._take(path, self.folder / "read" if answered else self.failed_folder)
                if taken is not None:
                    recovered.append((owner, taken, answered))
        return recovered

    def find_reply(self, message_id: str) -> dict | None:
        """A message in this inbox (unread or read) that replies to MESSAGE_ID, if any."""
        for path in self._files(self.folder) + self._files(self.folder / "read"):
            try:
                message = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if message.get("reply_to") == message_id:
                return message
        return None


def _attach(file_ids: list[str], to: str) -> list[dict]:
    """Check the file ids, share the files with TO and return the attachment entries {id, name, size, mime}."""
    from geenii.ibc.files import FileStore  # lazy: files imports this module

    if isinstance(file_ids, str):
        file_ids = [file_ids]
    file_ids = list(dict.fromkeys(f.strip() for f in file_ids if isinstance(f, str) and f.strip()))
    if len(file_ids) > MAX_ATTACHMENTS:
        raise ValueError(f"Too many attachments ({len(file_ids)}, max {MAX_ATTACHMENTS})")
    store = FileStore()
    metas = [store.info(file_id) for file_id in file_ids]  # all must exist before anything is shared
    check_agent_name(to)
    return [
        {k: meta[k] for k in ("id", "name", "size", "mime")}
        for meta in (store.share(m["id"], [to]) for m in metas)
    ]


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
    return "\n\n".join(f"[{e['ts']}] {e['author']} on {e['topic']}:\n{e['text']}" for e in entries)


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
        "Read the latest blackboard entries, optionally for one topic. With no entries it lists the topics.",
        params(
            topic=string("Only entries with this topic (empty for all)"),
            limit=integer("Maximum number of entries, default 20"),
        ),
    ),
    "send_mail": (
        "Send a direct message to another agent's inbox (or to 'human').",
        params(
            to=string("Receiver agent name, see list_agents"),
            subject=string("Subject line"),
            body=string("Message text"),
            reply_to=string("Id of the message this replies to, if any"),
            attachments=array(string("File id"), "Ids of stored files to attach (see file_upload)"),
            required=["to", "subject", "body"],
        ),
    ),
    "check_inbox": (
        "Fetch your new agent mail (full messages). Fetched messages are marked read.",
        params(),
    ),
    "read_mail": (
        "Open a message by id again, including ones already fetched.",
        params(message_id=string("Message id from check_inbox"), required=["message_id"]),
    ),
    "list_agents": (
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

    def blackboard_read(topic: str = "", limit: int = 20) -> dict:
        entries = board.read(topic=topic or None, limit=limit)
        return {"entries": entries} if entries else {"entries": [], "topics": board.topics()}

    def send_mail(to: str, subject: str, body: str, reply_to: str = "", attachments: list[str] | None = None) -> dict:
        to = to.strip().lower()
        if to == agent_name:
            raise ValueError("You can't send mail to yourself")
        if to not in known_agents():
            raise ValueError(f"Unknown agent {to!r}. Known: {', '.join(sorted(known_agents()))}")
        message = Mailbox.send(agent_name, to, subject, body, reply_to=reply_to or None, attachments=attachments)
        result = {"sent": True, "id": message["id"], "to": to}
        if message.get("attachments"):
            result["attachments"] = [a["id"] for a in message["attachments"]]
        return result

    def check_inbox() -> dict:
        # deliver unread mail in full and mark it read, so the same message is never handled twice
        messages = [mailbox.read(h["id"]) for h in mailbox.list()]
        if not messages:
            return {"new_messages": [], "note": "No new mail."}
        return {"new_messages": messages}

    def read_mail(message_id: str) -> dict:
        return mailbox.read(message_id)

    def list_agents() -> dict:
        return {name: desc for name, desc in known_agents().items() if name != agent_name}

    handlers = {
        "blackboard_post": blackboard_post,
        "blackboard_read": blackboard_read,
        "send_mail": send_mail,
        "check_inbox": check_inbox,
        "read_mail": read_mail,
        "list_agents": list_agents,
    }
    return [
        PythonFunctionTool(name, description, parameters, handlers[name])
        for name, (description, parameters) in COMMS_TOOL_DEFS.items()
    ]
