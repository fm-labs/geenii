"""How agents share files: one store of immutable files, each referenced by an id.

    GEENII_HOME/files/
    └── f_<32 hex>/
        ├── data        # the file's bytes, never changed after upload
        ├── meta.json   # id, name, size, sha256, mime, owner, created_at, shared_with, note
        └── .lock       # held while meta.json is updated (sharing)

An upload is written to a hidden temp folder and renamed into place, so nobody sees a half-written file. A
changed file is uploaded again and gets a new id, so an id always means the same content.

The id is the key: whoever knows it can read the file. All agents run as the same OS user, so finer access
checks would not add real security. Only the owner (or the human through the CLI) deletes a file.

An agent's *filebox* is a view, not a folder: the files it uploaded plus the ones shared with it, which is
what attaching a file to agent mail does (see Mailbox.send).
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import shutil
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from geenii.config import geenii_home
from geenii.ibc.comms import MAX_TEXT, _locked, check_agent_name
from geenii.utils.schema import boolean, params, string

FILE_ID_RE = re.compile(r"^f_[0-9a-f]{32}$")
MAX_FILE_SIZE = 25 * 1024 * 1024
MAX_NAME = 200
MAX_NOTE = 1000
_CHUNK = 1024 * 1024


def files_dir() -> Path:
    return geenii_home() / "files"


def check_file_id(file_id: str) -> str:
    """Return the id if it is a valid file id, else raise ValueError (ids become folder names)."""
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


def _write_json(path: Path, data: dict) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


class FileStore:
    def __init__(self, root: Path | None = None):
        self._root = root

    @property
    def root(self) -> Path:
        return self._root or files_dir()

    def _folder(self, file_id: str) -> Path:
        return self.root / check_file_id(file_id)

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
        import io

        return self._store(owner, io.BytesIO(data), name, note)

    def put_text(self, owner: str, name: str, text: str, note: str = "") -> dict:
        if not isinstance(text, str):
            raise ValueError("Text must be a string")
        return self.put_bytes(owner, text.encode("utf-8"), name, note)

    def _store(self, owner: str, stream, name: str, note: str) -> dict:
        owner = check_agent_name(owner)
        name = clean_name(name)
        note = (note or "").strip()
        if len(note) > MAX_NOTE:
            raise ValueError(f"Note is too long ({len(note)} characters, max {MAX_NOTE})")
        file_id = f"f_{uuid.uuid4().hex}"
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.root / f".tmp-{file_id}"
        tmp.mkdir()
        try:
            digest, size = hashlib.sha256(), 0
            with open(tmp / "data", "wb") as out:
                while chunk := stream.read(_CHUNK):
                    size += len(chunk)
                    if size > MAX_FILE_SIZE:
                        raise ValueError(f"File is too large (more than {MAX_FILE_SIZE} bytes)")
                    digest.update(chunk)
                    out.write(chunk)
            meta = {
                "id": file_id,
                "name": name,
                "size": size,
                "sha256": digest.hexdigest(),
                "mime": mimetypes.guess_type(name)[0] or "application/octet-stream",
                "owner": owner,
                "created_at": _now().isoformat(timespec="seconds"),
                "shared_with": [],
                "note": note,
            }
            _write_json(tmp / "meta.json", meta)
            os.replace(tmp, self.root / file_id)  # atomic: the file appears complete or not at all
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        return meta

    def share(self, file_id: str, agents: list[str]) -> dict:
        """Add AGENTS to the file's shared_with, so it shows in their filebox. Returns the metadata."""
        agents = [check_agent_name(a) for a in agents]
        folder = self._folder(file_id)
        if not (folder / "meta.json").is_file():
            raise ValueError(f"No file {file_id}")
        with open(folder / ".lock", "a") as lock, _locked(lock, exclusive=True):
            meta = self.info(file_id)
            added = [a for a in agents if a != meta["owner"] and a not in meta["shared_with"]]
            if added:
                meta["shared_with"] = meta["shared_with"] + added
                _write_json(folder / "meta.json", meta)
        return meta

    def delete(self, file_id: str, by: str | None = None) -> None:
        """Delete a file. BY, if given, must be its owner; None deletes as the human admin (CLI, gc)."""
        meta = self.info(file_id)
        if by is not None and by != meta["owner"]:
            raise ValueError(f"Only the owner ({meta['owner']}) can delete {file_id}")
        trash = self.root / f".trash-{file_id}-{uuid.uuid4().hex[:8]}"
        try:
            os.replace(self._folder(file_id), trash)  # atomic: readers see the whole file or no file
        except FileNotFoundError:
            raise ValueError(f"No file {file_id}")
        shutil.rmtree(trash, ignore_errors=True)

    # -- reading -------------------------------------------------------------

    def info(self, file_id: str) -> dict:
        path = self._folder(file_id) / "meta.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ValueError(f"No file {file_id}")
        except (OSError, json.JSONDecodeError) as e:
            raise ValueError(f"File {file_id} is damaged: {e}")

    def exists(self, file_id: str) -> bool:
        try:
            return (self._folder(file_id) / "meta.json").is_file()
        except ValueError:
            return False

    def data_path(self, file_id: str) -> Path:
        self.info(file_id)
        return self._folder(file_id) / "data"

    def read_bytes(self, file_id: str) -> bytes:
        return self.data_path(file_id).read_bytes()

    def read_text(self, file_id: str, limit: int = MAX_TEXT) -> tuple[str, bool]:
        """The file as UTF-8 text, cut to LIMIT characters; (text, truncated). ValueError for binary files."""
        meta = self.info(file_id)
        with open(self.data_path(file_id), "rb") as f:
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
        shutil.copyfile(self.data_path(file_id), dest)
        return dest

    def list(self, agent: str | None = None) -> list[dict]:
        """Metadata of all files, newest first; with AGENT only its filebox (owned by or shared with it)."""
        if not self.root.is_dir():
            return []
        files = []
        for folder in self.root.iterdir():
            if not FILE_ID_RE.fullmatch(folder.name):
                continue
            try:
                meta = self.info(folder.name)
            except ValueError:
                continue  # removed meanwhile, or damaged
            if agent is None or meta.get("owner") == agent or agent in meta.get("shared_with", []):
                files.append(meta)
        return sorted(files, key=lambda m: (m.get("created_at", ""), m["id"]), reverse=True)

    def gc(self, older_than: timedelta, keep: set[str] | None = None) -> list[str]:
        """Delete files older than OLDER_THAN, except KEEP and files attached to mail nobody has read yet.

        Also removes leftover temp and trash folders of interrupted uploads and deletes. Returns deleted ids.
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
        if self.root.is_dir():
            for folder in self.root.iterdir():
                if folder.name.startswith((".tmp-", ".trash-")) and folder.is_dir():
                    if datetime.fromtimestamp(folder.stat().st_mtime, UTC) < cutoff:
                        shutil.rmtree(folder, ignore_errors=True)
        return deleted


def attached_to_pending_mail() -> set[str]:
    """Ids of files attached to mail that is unread or being handled by a worker."""
    ids: set[str] = set()
    inbox_root = geenii_home() / "inbox"
    if not inbox_root.is_dir():
        return ids
    for path in list(inbox_root.glob("*/*.json")) + list(inbox_root.glob("*/processing/*/*.json")):
        try:
            message = json.loads(path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            continue
        for a in message.get("attachments") or []:
            if isinstance(a, dict) and a.get("id"):
                ids.add(a["id"])
    return ids


def format_size(size: int) -> str:
    for unit in ("B", "KB", "MB"):
        if size < 1024 or unit == "MB":
            return f"{size} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size} B"


def format_attachments(attachments: list[dict]) -> str:
    return "\n".join(f"- {a.get('name')} ({a.get('id')}, {format_size(a.get('size') or 0)})" for a in attachments)


# -- tools bound to one agent ---------------------------------------------------

_FILE_ID_PARAM = string("File id, e.g. f_3f9c...")

# name -> (description, parameters) of the file tools; shared by files_tools() and the stubs in ibc/tools.py
FILE_TOOL_DEFS: dict[str, tuple[str, dict]] = {
    "file_upload": (
        "Upload a file from your working folder to the shared file store. Returns its id, which you can "
        "attach to agent mail (send_mail attachments) or mention to other agents.",
        params(
            path=string("File path, relative to your working folder"),
            note=string("Optional short description"),
            required=["path"],
        ),
    ),
    "file_download": (
        "Copy a file from the shared file store into your working folder.",
        params(
            file_id=_FILE_ID_PARAM,
            path=string("Where to save it, relative to your working folder (default: its own name)"),
            overwrite=boolean("Replace an existing file, default false"),
            required=["file_id"],
        ),
    ),
    "file_list": (
        "List your filebox: the files you uploaded and the files other agents shared with you.",
        params(),
    ),
    "file_info": (
        "Show a stored file's name, size, type, owner and note, without its content.",
        params(file_id=_FILE_ID_PARAM, required=["file_id"]),
    ),
    "file_save_text": (
        "Save text as a new file in the shared file store (no working folder needed). Returns its id.",
        params(
            name=string("File name, e.g. report.md"),
            text=string("The file content"),
            note=string("Optional short description"),
            required=["name", "text"],
        ),
    ),
    "file_read_text": (
        f"Read a stored text file (up to {MAX_TEXT} characters). For binary or longer files use file_download.",
        params(file_id=_FILE_ID_PARAM, required=["file_id"]),
    ),
}

FILE_TOOL_NAMES = frozenset(FILE_TOOL_DEFS)


def files_tools(agent_name: str, store: FileStore | None = None):
    """The file store tools for one agent. Uploads are owned by `agent_name`; paths are relative to the agent's
    working folder and must pass the same checks as the `read` and `write` tools."""
    from geenii.tool.common import ToolCallContext, to_tool_call_result
    from geenii.tool.computer import _normalize_path, is_file_in_allowed_dirs
    from geenii.tool.python import PythonFunctionTool

    check_agent_name(agent_name)
    store = store or FileStore()

    class AgentFileTool(PythonFunctionTool):
        """A function tool whose handler also gets the agent's working folder as `cwd`."""

        def invoke(self, args, env=None, *, ctx: ToolCallContext):
            try:
                return to_tool_call_result(self.handler(cwd=ctx.cwd, **args))
            except Exception as e:
                return to_tool_call_result(e)

    def _allowed(path: str, cwd: str | None, what: str) -> Path:
        base = cwd or os.getcwd()
        resolved = _normalize_path(path, base)
        if not is_file_in_allowed_dirs(resolved, base):
            raise ValueError(f"You are not allowed to {what} this file: {resolved}")
        return Path(resolved)

    def _summary(meta: dict) -> dict:
        return {k: meta.get(k) for k in ("id", "name", "size", "mime", "owner", "created_at", "note")}

    def file_upload(path: str, note: str = "", cwd: str | None = None) -> dict:
        return _summary(store.put(agent_name, _allowed(path, cwd, "upload"), note=note))

    def file_download(file_id: str, path: str = "", overwrite: bool = False, cwd: str | None = None) -> dict:
        meta = store.info(file_id)
        dest = _allowed(path or meta["name"], cwd, "write")
        dest = store.copy_to(file_id, dest, overwrite=bool(overwrite))
        if not is_file_in_allowed_dirs(dest, cwd or os.getcwd()):  # a directory DEST got the file's name
            dest.unlink(missing_ok=True)
            raise ValueError(f"You are not allowed to write this file: {dest}")
        return {"saved": str(dest), "id": meta["id"], "name": meta["name"], "size": meta["size"]}

    def file_list(cwd: str | None = None) -> dict:
        files = store.list(agent_name)
        return (
            {"files": [_summary(m) | {"shared": m.get("owner") != agent_name} for m in files]}
            if files
            else {"files": [], "note": "Your filebox is empty."}
        )

    def file_info(file_id: str, cwd: str | None = None) -> dict:
        meta = store.info(file_id)
        return _summary(meta) | {"sha256": meta["sha256"], "shared_with": meta.get("shared_with", [])}

    def file_save_text(name: str, text: str, note: str = "", cwd: str | None = None) -> dict:
        return _summary(store.put_text(agent_name, name, text, note=note))

    def file_read_text(file_id: str, cwd: str | None = None) -> dict:
        meta = store.info(file_id)
        text, truncated = store.read_text(file_id)
        result = {"id": meta["id"], "name": meta["name"], "text": text}
        if truncated:
            result["truncated"] = f"Only the first {len(text)} characters; download the file for all of it."
        return result

    handlers = {
        "file_upload": file_upload,
        "file_download": file_download,
        "file_list": file_list,
        "file_info": file_info,
        "file_save_text": file_save_text,
        "file_read_text": file_read_text,
    }
    return [
        AgentFileTool(name, description, parameters, handlers[name])
        for name, (description, parameters) in FILE_TOOL_DEFS.items()
    ]
