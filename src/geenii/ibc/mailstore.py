"""Where agent mail and channel posts are stored: the MailboxStore protocol and its SQLite implementation.

geenii.ibc.comms checks names and texts and builds messages; a MailboxStore only keeps them. A message is the
dict Mailbox.send builds ({id, ts, from, to, subject, body, reply_to, attachments?}). It is stored under its
recipient: an agent name for direct mail, or a channel name starting with '@' (e.g. '@blackboard').

Direct mail is in one of four states:

    unread      delivered, nobody took it yet
    processing  claimed by an owner (a worker instance) that is working on it
    read        taken without an owner, or finished by its owner (ack)
    failed      not answered (fail, or recovered from an owner that died)

A channel post is shared by every reader, so it has no per-reader state: it is `posted`. Each agent instead
has a cursor per channel, the position of the last post it has seen. Cursors are opaque, increasing integers
(insert order), not timestamps: timestamps tie and depend on the sender's clock.

A store must make every state change atomic: when several processes claim from one inbox, each message goes
to exactly one of them, finishing a message works only for the owner that holds it, and a cursor never moves
backwards.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from geenii.config import geenii_home

UNREAD = "unread"
PROCESSING = "processing"
READ = "read"
FAILED = "failed"
POSTED = "posted"
STATES = (UNREAD, PROCESSING, READ, FAILED, POSTED)


@runtime_checkable
class MailboxStore(Protocol):
    """Storage for agent mail and channel posts. Implementations must be safe to use from several threads and
    processes."""

    # -- direct mail

    def deliver(self, message: dict) -> None:
        """Store a new message as unread in the inbox of message['to'] (an agent)."""
        ...

    def messages(self, agent: str, states: tuple[str, ...] = (UNREAD,)) -> list[tuple[dict, str, str | None]]:
        """(message, state, owner) of AGENT's messages in the given states, oldest first."""
        ...

    def get(self, agent: str, message_id: str) -> tuple[dict, str, str | None] | None:
        """(message, state, owner) of one of AGENT's messages, or None."""
        ...

    def mark_read(self, agent: str, message_id: str) -> bool:
        """Move an unread message to read; False if it isn't unread (anymore)."""
        ...

    def claim_next(self, agent: str, owner: str | None = None) -> dict | None:
        """Take AGENT's oldest unread message: to processing under OWNER, or to read without one."""
        ...

    def finish(self, agent: str, message_id: str, owner: str, state: str) -> bool:
        """Move a message OWNER holds to STATE (read or failed); False if OWNER doesn't hold it."""
        ...

    def owners(self, agent: str) -> list[str]:
        """Owners that hold processing messages of AGENT."""
        ...

    def find_reply(self, agent: str, message_id: str) -> dict | None:
        """A message in AGENT's inbox (any state) that replies to MESSAGE_ID, if any."""
        ...

    def pending_attachment_ids(self) -> set[str]:
        """File ids attached to unread or processing messages of any agent."""
        ...

    # -- channels

    def post(self, message: dict) -> int:
        """Store a post in the channel message['to']; returns its cursor."""
        ...

    def channel_messages(self, channel: str, after: int | None = None, subject: str | None = None,
                         sender: str | None = None, limit: int = 20) -> list[tuple[int, dict]]:
        """(cursor, message) of posts, oldest first. With AFTER: the first LIMIT posts after that cursor;
        without: the latest LIMIT posts. SUBJECT matches case-insensitively."""
        ...

    def channel_end(self, channel: str) -> int:
        """The cursor of the newest post in CHANNEL (0 if it has none)."""
        ...

    def subjects(self, channel: str) -> dict[str, int]:
        """Number of posts per subject, in order of first use."""
        ...

    def channels(self) -> dict[str, int]:
        """Number of posts per channel."""
        ...

    def get_cursor(self, channel: str, agent: str) -> int | None:
        """The cursor of the last post AGENT has seen in CHANNEL, or None if it never read the channel."""
        ...

    def advance_cursor(self, channel: str, agent: str, cursor: int) -> None:
        """Move AGENT's cursor in CHANNEL forward to CURSOR (never backwards)."""
        ...


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


SCHEMA_VERSION = 1

_SCHEMA = [
    """CREATE TABLE IF NOT EXISTS messages (
        seq        INTEGER PRIMARY KEY AUTOINCREMENT,
        id         TEXT NOT NULL UNIQUE,
        recipient  TEXT NOT NULL,
        reply_to   TEXT,
        state      TEXT NOT NULL DEFAULT 'unread',
        owner      TEXT,
        updated_at TEXT NOT NULL,
        subject    TEXT NOT NULL,
        body       TEXT NOT NULL,
        metadata   TEXT NOT NULL
    )""",
    "CREATE INDEX IF NOT EXISTS messages_inbox ON messages (recipient, state, seq)",
    "CREATE INDEX IF NOT EXISTS messages_reply ON messages (recipient, reply_to)",
    """CREATE TABLE IF NOT EXISTS channel_cursors (
        channel    TEXT NOT NULL,
        agent      TEXT NOT NULL,
        last_seq   INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (channel, agent)
    )""",
]


_COLUMNS = "subject, body, metadata"  # what _message rebuilds a message from


def _message(subject: str, body: str, metadata: str) -> dict:
    """Rebuild a message from its row: subject and body have their own columns, the rest is in metadata."""
    message = json.loads(metadata)
    message["subject"] = subject
    message["body"] = body
    return message


class SqliteMailboxStore:
    """All inboxes and channels in one SQLite database (default GEENII_HOME/mail.db, resolved on every use).

    Each call opens its own connection, so one store can be shared by threads; WAL mode and a busy timeout
    let several processes read and write at once.
    """

    def __init__(self, path: Path | str | None = None, timeout: float = 30.0):
        self._path = Path(path) if path is not None else None
        self.timeout = timeout

    @property
    def path(self) -> Path:
        return self._path or geenii_home() / "mail.db"

    @contextmanager
    def _connect(self):
        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=self.timeout, isolation_level=None)  # autocommit; explicit BEGIN
        try:
            if conn.execute("PRAGMA user_version").fetchone()[0] < SCHEMA_VERSION:
                self._create_schema(conn)
            yield conn
        finally:
            conn.close()

    @staticmethod
    def _create_schema(conn: sqlite3.Connection) -> None:
        """Create the tables of a new database; the version in user_version marks it as done."""
        conn.execute("PRAGMA journal_mode=WAL")  # stored in the database file
        conn.execute("BEGIN IMMEDIATE")
        try:
            if conn.execute("PRAGMA user_version").fetchone()[0] < SCHEMA_VERSION:  # another process may have won
                for statement in _SCHEMA:
                    conn.execute(statement)
                conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        conn.execute("COMMIT")

    @contextmanager
    def _transaction(self):
        """A write transaction that takes the write lock up front, so check-then-update can't race."""
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
            except BaseException:
                conn.execute("ROLLBACK")
                raise
            conn.execute("COMMIT")

    def _insert(self, message: dict, state: str) -> int:
        metadata = {k: v for k, v in message.items() if k not in ("subject", "body")}
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO messages (id, recipient, reply_to, state, updated_at, subject, body, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (message["id"], message["to"], message.get("reply_to"), state, _now(),
                 message["subject"], message["body"], json.dumps(metadata, ensure_ascii=False)),
            )
        return cur.lastrowid

    # -- direct mail

    def deliver(self, message: dict) -> None:
        self._insert(message, UNREAD)

    def messages(self, agent: str, states: tuple[str, ...] = (UNREAD,)) -> list[tuple[dict, str, str | None]]:
        if not states:
            return []
        marks = ", ".join("?" * len(states))
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT {_COLUMNS}, state, owner FROM messages "
                f"WHERE recipient = ? AND state IN ({marks}) ORDER BY seq",
                (agent, *states),
            ).fetchall()
        return [(_message(*row[:3]), row[3], row[4]) for row in rows]

    def get(self, agent: str, message_id: str) -> tuple[dict, str, str | None] | None:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT {_COLUMNS}, state, owner FROM messages WHERE recipient = ? AND id = ?", (agent, message_id)
            ).fetchone()
        return (_message(*row[:3]), row[3], row[4]) if row else None

    def mark_read(self, agent: str, message_id: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE messages SET state = ?, updated_at = ? WHERE recipient = ? AND id = ? AND state = ?",
                (READ, _now(), agent, message_id, UNREAD),
            )
        return cur.rowcount == 1

    def claim_next(self, agent: str, owner: str | None = None) -> dict | None:
        with self._transaction() as conn:
            row = conn.execute(
                f"SELECT seq, {_COLUMNS} FROM messages WHERE recipient = ? AND state = ? ORDER BY seq LIMIT 1",
                (agent, UNREAD),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE messages SET state = ?, owner = ?, updated_at = ? WHERE seq = ?",
                (PROCESSING if owner is not None else READ, owner, _now(), row[0]),
            )
        return _message(*row[1:])

    def finish(self, agent: str, message_id: str, owner: str, state: str) -> bool:
        if state not in (READ, FAILED):
            raise ValueError(f"A finished message is read or failed, not {state!r}")
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE messages SET state = ?, updated_at = ? "
                "WHERE recipient = ? AND id = ? AND state = ? AND owner = ?",
                (state, _now(), agent, message_id, PROCESSING, owner),
            )
        return cur.rowcount == 1

    def owners(self, agent: str) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT DISTINCT owner FROM messages WHERE recipient = ? AND state = ? ORDER BY owner",
                (agent, PROCESSING),
            ).fetchall()
        return [owner for (owner,) in rows if owner]

    def find_reply(self, agent: str, message_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                f"SELECT {_COLUMNS} FROM messages WHERE recipient = ? AND reply_to = ? ORDER BY seq LIMIT 1",
                (agent, message_id),
            ).fetchone()
        return _message(*row) if row else None

    def pending_attachment_ids(self) -> set[str]:
        if not self.path.exists():
            return set()
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT j.value ->> 'id' FROM messages, json_each(messages.metadata, '$.attachments') AS j "
                "WHERE messages.state IN (?, ?)",
                (UNREAD, PROCESSING),
            ).fetchall()
        return {file_id for (file_id,) in rows if file_id}

    # -- channels

    def post(self, message: dict) -> int:
        return self._insert(message, POSTED)

    def channel_messages(self, channel: str, after: int | None = None, subject: str | None = None,
                         sender: str | None = None, limit: int = 20) -> list[tuple[int, dict]]:
        where, args = ["recipient = ?", "state = ?"], [channel, POSTED]
        if after is not None:
            where.append("seq > ?")
            args.append(int(after))
        if subject:
            where.append("lower(subject) = lower(?)")
            args.append(subject.strip())
        if sender:
            where.append("metadata ->> '$.from' = ?")
            args.append(sender)
        order = "ASC" if after is not None else "DESC"  # first posts after the cursor, or the latest posts
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT seq, {_COLUMNS} FROM messages WHERE {' AND '.join(where)} ORDER BY seq {order} LIMIT ?",
                (*args, max(1, int(limit))),
            ).fetchall()
        return [(row[0], _message(*row[1:])) for row in sorted(rows, key=lambda row: row[0])]

    def channel_end(self, channel: str) -> int:
        with self._connect() as conn:
            (end,) = conn.execute(
                "SELECT COALESCE(MAX(seq), 0) FROM messages WHERE recipient = ? AND state = ?", (channel, POSTED)
            ).fetchone()
        return end

    def subjects(self, channel: str) -> dict[str, int]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT subject, COUNT(*) FROM messages WHERE recipient = ? AND state = ? "
                "GROUP BY subject ORDER BY MIN(seq)",
                (channel, POSTED),
            ).fetchall()
        return dict(rows)

    def channels(self) -> dict[str, int]:
        if not self.path.exists():
            return {}
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT recipient, COUNT(*) FROM messages WHERE state = ? GROUP BY recipient ORDER BY recipient",
                (POSTED,),
            ).fetchall()
        return dict(rows)

    def get_cursor(self, channel: str, agent: str) -> int | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT last_seq FROM channel_cursors WHERE channel = ? AND agent = ?", (channel, agent)
            ).fetchone()
        return row[0] if row else None

    def advance_cursor(self, channel: str, agent: str, cursor: int) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO channel_cursors (channel, agent, last_seq, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT (channel, agent) DO UPDATE SET "
                "last_seq = MAX(last_seq, excluded.last_seq), updated_at = excluded.updated_at",
                (channel, agent, int(cursor), _now()),
            )


def default_mailbox_store() -> MailboxStore:
    """The store Mailbox and Channel use when none is given."""
    return SqliteMailboxStore()
