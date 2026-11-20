"""How agents share files: one store of immutable files, each referenced by an id.

FileStore checks owners, names, sizes and ids, builds the metadata and applies the rules below; where the
bytes and metadata are kept is up to a FileStorageAdapter (geenii.storage.filestorage). The default,
LocalFileStorage, keeps them in GEENII_HOME/files.

A changed file is uploaded again and gets a new id, so an id always means the same content.

The id is the key: whoever knows it can read the file. All agents run as the same OS user, so finer access
checks would not add real security. Only the owner (or the human through the CLI) deletes a file.

An agent's *filebox* is a view, not a folder: the files it uploaded plus the ones shared with it, which is
what attaching a file to agent mail does (see Mailbox.send).
"""

from __future__ import annotations

import hashlib
import io
import mimetypes
import os
import re
import shutil
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import BinaryIO

from geenii.ibc.comms import MAX_TEXT, check_agent_name
from geenii.storage.filestorage import FileStorageAdapter, LocalFileStorage, default_file_storage

FILE_ID_RE = re.compile(r"^f_[0-9a-f]{32}$")
MAX_FILE_SIZE = 25 * 1024 * 1024
MAX_NAME = 200
MAX_NOTE = 1000


def check_file_id(file_id: str) -> str:
    """Return the id if it is a valid file id, else raise ValueError (ids become folder names or keys)."""
    file_id = file_id.strip() if isinstance(file_id, str) else file_id
    if not isinstance(file_id, str) or not FILE_ID_RE.fullmatch(file_id):
        raise ValueError(f"Invalid file id {file_id!r}")
    return file_id


def clean_name(name: str) -> str:
    """A safe file name: the last path segment, without control characters, at most MAX_NAME characters."""
    name = Path(str(name or "").replace("\\", "/")).name
    name = "".join(c for c in name if c.isprintable()).strip()
    if not name or name in (".", ".."):
        raise ValueError("File name must not be empty")
    if len(name) > MAX_NAME:
        stem, suffix = os.path.splitext(name)
        name = stem[: MAX_NAME - len(suffix)] + suffix
    return name


def _now() -> datetime:
    return datetime.now(UTC)


class _MeasuredReader(io.RawIOBase):
    """Wraps an upload stream: counts and hashes what is read, and stops once it exceeds MAX_FILE_SIZE."""

    def __init__(self, stream: BinaryIO):
        self._stream = stream
        self.size = 0
        self.sha256 = hashlib.sha256()

    def readable(self) -> bool:
        return True

    def read(self, size: int = -1) -> bytes:
        chunk = self._stream.read(size)
        self.size += len(chunk)
        if self.size > MAX_FILE_SIZE:
            raise ValueError(f"File is too large (more than {MAX_FILE_SIZE} bytes)")
        self.sha256.update(chunk)
        return chunk

    def readinto(self, buffer) -> int:
        chunk = self.read(len(buffer))
        buffer[: len(chunk)] = chunk
        return len(chunk)


class FileStore:
    """The shared file store. STORAGE keeps the files (default: default_file_storage()); ROOT is a shortcut
    for LocalFileStorage(root)."""

    def __init__(self, root: Path | None = None, storage: FileStorageAdapter | None = None):
        if root is not None and storage is not None:
            raise ValueError("Pass root or storage, not both")
        self.storage = storage or (LocalFileStorage(root) if root is not None else default_file_storage())

    # -- writing -------------------------------------------------------------

    def put(self, owner: str, src: str | Path, name: str | None = None, note: str = "") -> dict:
        """Copy the file SRC into the store and return its metadata."""
        src = Path(src)
        if not src.is_file():
            raise ValueError(f"Not a file: {src}")
        with open(src, "rb") as f:
            return self._store(owner, f, name or src.name, note)

    def put_bytes(self, owner: str, data: bytes, name: str, note: str = "") -> dict:
        if len(data) > MAX_FILE_SIZE:
            raise ValueError(f"File is too large ({len(data)} bytes, max {MAX_FILE_SIZE})")
        return self._store(owner, io.BytesIO(data), name, note)

    def put_text(self, owner: str, name: str, text: str, note: str = "") -> dict:
        if not isinstance(text, str):
            raise ValueError("Text must be a string")
        return self.put_bytes(owner, text.encode("utf-8"), name, note)

    def _store(self, owner: str, stream: BinaryIO, name: str, note: str) -> dict:
        owner = check_agent_name(owner)
        name = clean_name(name)
        note = (note or "").strip()
        if len(note) > MAX_NOTE:
            raise ValueError(f"Note is too long ({len(note)} characters, max {MAX_NOTE})")
        file_id = f"f_{uuid.uuid4().hex}"
        reader = _MeasuredReader(stream)

        def meta() -> dict:  # called by the storage once the whole stream is read
            return {
                "id": file_id,
                "name": name,
                "size": reader.size,
                "sha256": reader.sha256.hexdigest(),
                "mime": mimetypes.guess_type(name)[0] or "application/octet-stream",
                "owner": owner,
                "created_at": _now().isoformat(timespec="seconds"),
                "shared_with": [],
                "note": note,
            }

        return self.storage.create(file_id, reader, meta)

    def share(self, file_id: str, agents: list[str]) -> dict:
        """Add AGENTS to the file's shared_with, so it shows in their filebox. Returns the metadata."""
        agents = [check_agent_name(a) for a in agents]

        def add(meta: dict) -> dict | None:
            added = [a for a in agents if a != meta["owner"] and a not in meta["shared_with"]]
            return meta | {"shared_with": meta["shared_with"] + added} if added else None

        try:
            return self.storage.update_meta(check_file_id(file_id), add)
        except FileNotFoundError:
            raise ValueError(f"No file {file_id}")

    def delete(self, file_id: str, by: str | None = None) -> None:
        """Delete a file. BY, if given, must be its owner; None deletes as the human admin (CLI, gc)."""
        meta = self.info(file_id)
        if by is not None and by != meta["owner"]:
            raise ValueError(f"Only the owner ({meta['owner']}) can delete {file_id}")
        try:
            self.storage.delete(meta["id"])
        except FileNotFoundError:
            raise ValueError(f"No file {file_id}")

    # -- reading -------------------------------------------------------------

    def info(self, file_id: str) -> dict:
        try:
            return self.storage.read_meta(check_file_id(file_id))
        except FileNotFoundError:
            raise ValueError(f"No file {file_id}")

    def exists(self, file_id: str) -> bool:
        try:
            self.info(file_id)
            return True
        except ValueError:
            return False

    def open(self, file_id: str) -> BinaryIO:
        """The file's bytes as a binary stream; close it (use `with`)."""
        try:
            return self.storage.open(check_file_id(file_id))
        except FileNotFoundError:
            raise ValueError(f"No file {file_id}")

    def read_bytes(self, file_id: str) -> bytes:
        with self.open(file_id) as f:
            return f.read()

    def read_text(self, file_id: str, limit: int = MAX_TEXT) -> tuple[str, bool]:
        """The file as UTF-8 text, cut to LIMIT characters; (text, truncated). ValueError for binary files."""
        meta = self.info(file_id)
        with self.open(file_id) as f:
            data = f.read(limit * 4 + 4)  # a UTF-8 character has at most 4 bytes
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as e:
            if len(data) < meta["size"] and e.start >= len(data) - 4:
                text = data[: e.start].decode("utf-8")  # cut inside a character at the read limit
            else:
                raise ValueError(f"{meta['name']} ({file_id}) is not a text file; download it instead")
        truncated = len(text) > limit or len(data) < meta["size"]
        return text[:limit], truncated

    def copy_to(self, file_id: str, dest: str | Path, overwrite: bool = False) -> Path:
        """Copy the file to DEST (a file path, or a directory to put it in under its own name)."""
        meta = self.info(file_id)
        dest = Path(dest)
        if dest.is_dir():
            dest = dest / meta["name"]
        if dest.exists() and not overwrite:
            raise ValueError(f"{dest} already exists")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with self.open(file_id) as src, open(dest, "wb") as out:
            shutil.copyfileobj(src, out)
        return dest

    def list(self, agent: str | None = None) -> list[dict]:
        """Metadata of all files, newest first; with AGENT only its filebox (owned by or shared with it)."""
        files = []
        for file_id in self.storage.ids():
            if not FILE_ID_RE.fullmatch(file_id):
                continue
            try:
                meta = self.info(file_id)
            except ValueError:
                continue  # removed meanwhile, or damaged
            if agent is None or meta.get("owner") == agent or agent in meta.get("shared_with", []):
                files.append(meta)
        return sorted(files, key=lambda m: (m.get("created_at", ""), m["id"]), reverse=True)

    def gc(self, older_than: timedelta, keep: set[str] | None = None) -> list[str]:
        """Delete files older than OLDER_THAN, except KEEP and files attached to mail nobody has read yet.

        Also removes leftovers of interrupted uploads and deletes. Returns the deleted ids.
        """
        keep = set(keep or ()) | attached_to_pending_mail()
        cutoff = _now() - older_than
        deleted = []
        for meta in self.list():
            try:
                created = datetime.fromisoformat(meta["created_at"])
            except KeyError, TypeError, ValueError:
                continue
            if created < cutoff and meta["id"] not in keep:
                try:
                    self.delete(meta["id"])
                    deleted.append(meta["id"])
                except ValueError:
                    pass
        self.storage.purge_incomplete(cutoff)
        return deleted


def attached_to_pending_mail() -> set[str]:
    """Ids of files attached to mail that is unread or being handled by a worker."""
    from geenii.ibc.mailstore import default_mailbox_store

    return default_mailbox_store().pending_attachment_ids()


def format_size(size: int) -> str:
    for unit in ("B", "KB", "MB"):
        if size < 1024 or unit == "MB":
            return f"{size} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size} B"


def format_attachments(attachments: list[dict]) -> str:
    return "\n".join(f"- {a.get('name')} ({a.get('id')}, {format_size(a.get('size') or 0)})" for a in attachments)



