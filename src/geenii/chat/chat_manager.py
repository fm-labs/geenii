import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
import logging

from geenii import config
from geenii.chat.chat_models import ContentPart, Room, Member, ChatMessage, RoomType

logger = logging.getLogger(__name__)

# Stable namespace for DM room IDs — generated once, fixed forever.
_DM_NAMESPACE = uuid.UUID(config.CHAT_DM_NAMESPACE)
_GROUP_NAMESPACE = uuid.UUID(config.CHAT_GROUP_NAMESPACE)
_DB_PATH = config.CHAT_DB_PATH

def dm_room_id(user_a: str, user_b: str) -> str:
    """Return a stable, order-independent UUID for the DM room between two users."""
    key = ":".join(sorted([user_a, user_b]))
    return str(uuid.uuid5(_DM_NAMESPACE, key))

def group_room_id(room_key: str) -> str:
    """Return a stable UUID for a group room based on a unique room key."""
    return str(uuid.uuid5(_GROUP_NAMESPACE, room_key))

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def _verify_password(password: str, password_hash: str) -> bool:
    return _hash_password(password) == password_hash


def _serialize_content(content: list[ContentPart]) -> str:
    return json.dumps([part.model_dump() for part in content])


def _deserialize_content(raw: str) -> list[ContentPart]:
    from pydantic import TypeAdapter
    adapter = TypeAdapter(list[ContentPart])
    return adapter.validate_python(json.loads(raw))


def _row_to_room(row: sqlite3.Row) -> Room:
    d = dict(row)
    d["is_public"] = bool(d["is_public"])
    d.pop("password_hash", None)
    d.setdefault("room_type", "group")  # default for rows pre-dating the column
    return Room(**d)


def _row_to_message(row: sqlite3.Row) -> ChatMessage:
    d = dict(row)
    d["content"] = _deserialize_content(d["content"])
    return ChatMessage(**d)


class ChatManager:
    def __init__(self, db_path: str = _DB_PATH):
        logger.info(f"Connecting to {db_path}")
        try:
            self._conn = sqlite3.connect(db_path, check_same_thread=False)
            self._init_db()
        except sqlite3.OperationalError:
            logger.error(f"Failed to connect to database at {db_path}. Check if the path is correct and writable.")
            raise

    @property
    def conn(self):
        if not hasattr(self, "_conn") or self._conn is None:
            raise RuntimeError("Database connection is not initialized.")
        return self._conn

    def _init_db(self) -> None:
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS rooms (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                owner TEXT NOT NULL,
                is_public INTEGER NOT NULL DEFAULT 1,
                password_hash TEXT,
                room_type TEXT NOT NULL DEFAULT 'group',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id TEXT NOT NULL REFERENCES rooms(id),
                username TEXT NOT NULL,
                member_type TEXT NOT NULL DEFAULT 'user',
                status TEXT NOT NULL DEFAULT 'joined',
                joined_at TEXT NOT NULL,
                UNIQUE(room_id, username)
            );
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                room_id TEXT NOT NULL REFERENCES rooms(id),
                sender_id TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at INTEGER NOT NULL DEFAULT (strftime('%s', 'now') * 1000)
            );
            CREATE INDEX IF NOT EXISTS idx_messages_room ON messages(room_id, id);
        """)
        # Migration: add room_type to existing databases that pre-date the column.
        # try:
        #     self.conn.execute("ALTER TABLE rooms ADD COLUMN room_type TEXT NOT NULL DEFAULT 'group'")
        #     self.conn.commit()
        # except sqlite3.OperationalError:
        #     pass  # column already exists

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()

    # ---------- Rooms ----------

    def create_room(
        self,
        name: str,
        owner: str,
        is_public: bool = True,
        password: str | None = None,
        room_type: RoomType = "group",
        dm_peer: str | None = None,  # required when room_type == "dm"
        room_id: str | None = None,  # optional explicit ID (for testing or special cases)
    ) -> Room:
        if not room_id:
            if room_type == "dm":
                if not dm_peer:
                    raise ValueError("dm_peer is required for DM rooms")
                room_id = dm_room_id(owner, dm_peer)
            elif room_type == "group":
                if not dm_peer:
                    raise ValueError("dm_peer (room_key) is required for group rooms")
                room_key = dm_peer
                room_id = group_room_id(room_key)
            else:
                raise ValueError(f"Invalid room type {room_type}")

        if not room_id or not name or not owner:
            raise ValueError("id, name, and owner are required to create a room")
        if room_type not in ("group", "dm"):
            raise ValueError("room_type must be 'group' or 'dm'")

        password_hash = _hash_password(password) if password else None
        self.conn.execute(
            "INSERT INTO rooms (id, name, owner, is_public, password_hash, room_type, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (room_id, name, owner, int(is_public), password_hash, room_type, _now()),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
        return _row_to_room(row)

    def list_rooms(self) -> list[Room]:
        rows = self.conn.execute("SELECT * FROM rooms ORDER BY created_at").fetchall()
        return [_row_to_room(r) for r in rows]

    def get_room(self, room_id: str) -> Room | None:
        row = self.conn.execute("SELECT * FROM rooms WHERE id = ?", (room_id,)).fetchone()
        return _row_to_room(row) if row else None
    
    def get_dm_room(self, owner: str, peer: str, auto_create: bool = True, auto_join: bool = True) -> Room | None:
        room_id = dm_room_id(owner, peer)

        _room = self.get_room(room_id)
        if _room or not auto_create:
            # todo validate owner/is_public/room_type if room already exists?
            return _room

        # auto-create DM room
        logger.info("Auto-creating DM room %s for user %s with peer %s", room_id, owner, peer)
        _room = self.create_room(
            room_id=room_id, # pre-computed ID to ensure stability
            name=f"DM between {owner} and {peer}",
            owner=owner,
            is_public=False,
            room_type="dm",
            #dm_peer=peer
        )
        # auto-invite/join the peer to the DM room
        if auto_join:
            self.join_room(room_id, owner, member_type="bot" if owner.startswith("geenii:bot:") else "user")
            self.join_room(room_id, peer, member_type="bot" if peer.startswith("geenii:bot:") else "user")
        return _room

    def get_group_room(self, room_key: str, username: str = None, is_public: bool = False, auto_create: bool = False, auto_join: bool = True, members: set[str] = None) -> Room | None:
        """
        Get a group room by its unique room key. Optionally auto-create the room if it doesn't exist, and auto-join the user to the room.

        :param room_key: A unique key that identifies the group room (e.g. "project-123", "team-alpha", etc.)
        :param username: The username requesting the room. Required if auto_create or auto_join is True to set the owner and join the room.
        :param is_public: Whether the room should be publicly visible (default: False). Only applicable if auto_create is True.
        :param auto_create: Whether to auto-create the room if it doesn't exist (default: False). If True, username is required to set the owner and initial member of the room.
        :param auto_join: Whether to auto-join the user to the room if it already exists (default: True). If True, username is required to join the room.
        :param members: Optional list of additional usernames to auto-join to the room if auto_create is True. Ignored if auto_create is False.
        :return: The Room object if found or created, or None if not found and not auto-created.
        """
        members = members or set()
        room_id = group_room_id(room_key)
        _room = self.get_room(room_id)

        # auto-create group room
        if not _room and auto_create:
            if not username:
                raise ValueError("Username is required to auto-create a group room")
            logger.info("Auto-creating group room %s for user %s with room key %s", room_id, username, room_key)
            _room = self.create_room(
                room_id=room_id, # pre-computed ID to ensure stability
                name=f"Group Room {room_key}",
                owner="system", # todo implement group room ownership
                is_public=is_public, # todo implement public group rooms
                room_type="group",
                #dm_peer=room_key
            )
            # auto-join the creator to the group room
            self.join_room(room_id, username, member_type="bot" if username.startswith("geenii:bot:") else "user")
            return _room

        # not found and not auto-create, return None
        if not _room:
            return None

        # todo validate owner/is_public/room_type if room already exists?

        # auto-join the user to the group room
        if auto_join:
            if username:
                members.add(username)
            for peer in members:
                if peer and not self.is_member(room_id, peer):
                    self.join_room(room_id, peer, member_type="bot" if peer.startswith("geenii:bot:") else "user")

        return _room


    def get_room_password_hash(self, room_id: str) -> str | None:
        row = self.conn.execute("SELECT password_hash FROM rooms WHERE id = ?", (room_id,)).fetchone()
        return row["password_hash"] if row else None

    def get_room_owner(self, room_id: str) -> str | None:
        row = self.conn.execute("SELECT owner FROM rooms WHERE id = ?", (room_id,)).fetchone()
        return row["owner"] if row else None

    def verify_password(self, password: str, password_hash: str) -> bool:
        return _verify_password(password, password_hash)

    # ---------- Members ----------

    def join_room(self, room_id: str, username: str, member_type: str = "user") -> Member:
        existing = self.conn.execute(
            "SELECT * FROM members WHERE room_id = ? AND username = ?",
            (room_id, username),
        ).fetchone()

        if existing:
            if existing["status"] == "banned":
                raise sqlite3.IntegrityError("Banned from room")
            if existing["status"] != "joined":
                #raise sqlite3.IntegrityError("Already joined")
                self.conn.execute(
                    "UPDATE members SET status = 'joined', member_type = ?, joined_at = ? WHERE id = ?",
                    (member_type, _now(), existing["id"]),
                )
                self.conn.commit()
            row = self.conn.execute("SELECT * FROM members WHERE id = ?", (existing["id"],)).fetchone()
        else:
            cur = self.conn.execute(
                "INSERT INTO members (room_id, username, member_type, status, joined_at) VALUES (?, ?, ?, 'joined', ?)",
                (room_id, username, member_type, _now()),
            )
            self.conn.commit()
            row = self.conn.execute("SELECT * FROM members WHERE id = ?", (cur.lastrowid,)).fetchone()

        return Member(**dict(row))

    def leave_room(self, room_id: str, username: str) -> Member | None:
        existing = self.conn.execute(
            "SELECT * FROM members WHERE room_id = ? AND username = ? AND status = 'joined'",
            (room_id, username),
        ).fetchone()
        if not existing:
            return None
        self.conn.execute(
            "UPDATE members SET status = 'left' WHERE id = ?",
            (existing["id"],),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM members WHERE id = ?", (existing["id"],)).fetchone()
        return Member(**dict(row))

    def invite_user(self, room_id: str, username: str, member_type: str = "user") -> Member:
        cur = self.conn.execute(
            "INSERT INTO members (room_id, username, member_type, status, joined_at) VALUES (?, ?, ?, 'invited', ?)",
            (room_id, username, member_type, _now()),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM members WHERE id = ?", (cur.lastrowid,)).fetchone()
        return Member(**dict(row))

    def get_members(self, room_id: str, status: str | None = None) -> list[Member]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM members WHERE room_id = ? AND status = ? ORDER BY id",
                (room_id, status),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM members WHERE room_id = ? ORDER BY id", (room_id,)
            ).fetchall()
        return [Member(**dict(r)) for r in rows]

    def is_member(self, room_id: str, username: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM members WHERE room_id = ? AND username = ? AND status = 'joined'",
            (room_id, username),
        ).fetchone()
        return row is not None

    # ---------- Messages ----------

    def add_message(self, msg: ChatMessage) -> None:
        serialized = _serialize_content(msg.content)
        cur = self.conn.execute(
            "INSERT INTO messages (id, room_id, sender_id, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (msg.id, msg.room_id, msg.sender_id, serialized, msg.created_at),
        )
        self.conn.commit()
        #row = self.conn.execute("SELECT * FROM messages WHERE id = ?", (cur.lastrowid,)).fetchone()
        #return _row_to_message(row)

    # def add_message(self, room_id: str, sender_id: str, content: list[ContentPart]) -> ChatMessage:
    #     serialized = _serialize_content(content)
    #     cur = self.conn.execute(
    #         "INSERT INTO messages (room_id, sender_id, content, created_at) VALUES (?, ?, ?, ?)",
    #         (room_id, sender_id, serialized, _now()),
    #     )
    #     self.conn.commit()
    #     row = self.conn.execute("SELECT * FROM messages WHERE id = ?", (cur.lastrowid,)).fetchone()
    #     return _row_to_message(row)

    def get_messages(self, room_id: str, after: int | None = None) -> list[ChatMessage]:
        if after is not None:
            rows = self.conn.execute(
                "SELECT * FROM messages WHERE room_id = ? AND created_at > ? ORDER BY created_at ASC",
                (room_id, after),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM messages WHERE room_id = ? ORDER BY created_at ASC", (room_id,)
            ).fetchall()
        return [_row_to_message(r) for r in rows]
