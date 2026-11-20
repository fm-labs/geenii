"""Where shared files are kept: the FileStorageAdapter protocol and its local filesystem implementation.

geenii.ibc.filestore checks owners, names, sizes and ids and builds the metadata; a FileStorageAdapter only
keeps a file's bytes and its metadata dict, both under the file's id. Ids are already validated
(`f_` + 32 hex characters), so an adapter may use them as folder names, object keys or path segments.

A stored file's bytes never change. Only its metadata does (sharing adds agents to `shared_with`). An adapter
must make sure that:

- a file appears complete (bytes and metadata) or not at all, also when an upload fails halfway,
- a delete removes it completely, so readers see the whole file or no file,
- a metadata update is a read-modify-write that doesn't lose a concurrent update.

Adapters for remote storage (S3, FTP, WebDAV, ...) implement the same protocol; there are none yet.
"""

from __future__ import annotations

import json
import os
import shutil
import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO, Protocol, runtime_checkable

from geenii.config import geenii_home
from geenii.ibc.comms import _locked

_CHUNK = 1024 * 1024


@runtime_checkable
class FileStorageAdapter(Protocol):
    """Keeps file bytes and metadata by file id.

    Missing files raise FileNotFoundError; a file whose metadata can't be read raises ValueError.
    """

    def create(self, file_id: str, data: BinaryIO, meta: Callable[[], dict]) -> dict:
        """Store a new file: read DATA to the end, then call META for its metadata (it may depend on what was
        read, e.g. size and hash) and store both. The file must appear complete or not at all: if reading,
        META or writing raises, nothing is left behind and the error propagates. Returns the metadata."""
        ...

    def read_meta(self, file_id: str) -> dict:
        """The file's metadata."""
        ...

    def update_meta(self, file_id: str, change: Callable[[dict], dict | None]) -> dict:
        """Call CHANGE with the current metadata and store what it returns (None: no change), atomically with
        respect to other updates. Returns the metadata as stored."""
        ...

    def open(self, file_id: str) -> BinaryIO:
        """The file's bytes as a readable binary stream (a context manager); the caller closes it."""
        ...

    def delete(self, file_id: str) -> None:
        """Remove the file's bytes and metadata."""
        ...

    def ids(self) -> Iterator[str]:
        """The ids of all complete files, in any order."""
        ...

    def purge_incomplete(self, before: datetime) -> None:
        """Remove leftovers of uploads and deletes that were interrupted before BEFORE."""
        ...


def _write_json(path: Path, data: dict) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


class LocalFileStorage:
    """Files in a local folder (default GEENII_HOME/files, resolved on every call), one subfolder per file:

        <root>/
        ├── f_<32 hex>/
        │   ├── data        # the file's bytes
        │   ├── meta.json   # the metadata
        │   └── .lock       # held while meta.json is updated
        ├── .tmp-f_…/       # an upload in progress (ignored)
        └── .trash-f_…-…/   # a delete in progress (ignored)

    An upload is written to a temp folder and renamed into place; a delete renames the folder to a trash
    folder first. Both renames are atomic on one filesystem. Metadata updates hold an fcntl lock, so this
    works for several processes on one machine (and not on network filesystems without working locks).
    """

    def __init__(self, root: str | Path | None = None):
        self._root = Path(root) if root is not None else None

    @property
    def root(self) -> Path:
        return self._root or geenii_home() / "files"

    def _folder(self, file_id: str) -> Path:
        return self.root / file_id

    def create(self, file_id: str, data: BinaryIO, meta: Callable[[], dict]) -> dict:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.root / f".tmp-{file_id}"
        tmp.mkdir()
        try:
            with open(tmp / "data", "wb") as out:
                shutil.copyfileobj(data, out, _CHUNK)
            stored = meta()
            _write_json(tmp / "meta.json", stored)
            os.replace(tmp, self._folder(file_id))  # atomic: the file appears complete or not at all
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        return stored

    def read_meta(self, file_id: str) -> dict:
        path = self._folder(file_id) / "meta.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise
        except (OSError, json.JSONDecodeError) as e:
            raise ValueError(f"File {file_id} is damaged: {e}")

    def update_meta(self, file_id: str, change: Callable[[dict], dict | None]) -> dict:
        folder = self._folder(file_id)
        if not (folder / "meta.json").is_file():
            raise FileNotFoundError(file_id)
        with open(folder / ".lock", "a") as lock, _locked(lock, exclusive=True):
            meta = self.read_meta(file_id)
            changed = change(dict(meta))
            if changed is None:
                return meta
            _write_json(folder / "meta.json", changed)
            return changed

    def open(self, file_id: str) -> BinaryIO:
        if not (self._folder(file_id) / "meta.json").is_file():
            raise FileNotFoundError(file_id)
        return open(self._folder(file_id) / "data", "rb")

    def delete(self, file_id: str) -> None:
        trash = self.root / f".trash-{file_id}-{uuid.uuid4().hex[:8]}"
        os.replace(self._folder(file_id), trash)  # atomic: readers see the whole file or no file
        shutil.rmtree(trash, ignore_errors=True)

    def ids(self) -> Iterator[str]:
        if not self.root.is_dir():
            return
        for folder in self.root.iterdir():
            if not folder.name.startswith(".") and folder.is_dir():
                yield folder.name

    def purge_incomplete(self, before: datetime) -> None:
        if not self.root.is_dir():
            return
        for folder in self.root.iterdir():
            if folder.name.startswith((".tmp-", ".trash-")) and folder.is_dir():
                if datetime.fromtimestamp(folder.stat().st_mtime, UTC) < before:
                    shutil.rmtree(folder, ignore_errors=True)


def default_file_storage() -> FileStorageAdapter:
    return LocalFileStorage()
