"""The file storage adapter (geenii.storage.filestorage): the protocol and LocalFileStorage."""

import io
import json
import os
import threading
import time
from datetime import UTC, datetime, timedelta

import pytest

from geenii.storage.filestorage import FileStorageAdapter, LocalFileStorage, default_file_storage

ID_A = "f_" + "a" * 32
ID_B = "f_" + "b" * 32


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    path = tmp_path / "geenii-home"
    monkeypatch.setenv("GEENII_HOME", str(path))
    return path


@pytest.fixture
def root(tmp_path):
    return tmp_path / "files"


@pytest.fixture
def storage(root):
    return LocalFileStorage(root)


def meta_for(file_id, **extra):
    return lambda: {"id": file_id, "shared_with": [], **extra}


def entries(root):
    return sorted(p.name for p in root.iterdir()) if root.exists() else []


class FailingStream(io.RawIOBase):
    """Yields some bytes, then fails like a broken connection or an upload over the size limit."""

    def __init__(self, error: BaseException):
        self.error, self.sent = error, False

    def readable(self):
        return True

    def read(self, size=-1):
        if not self.sent:
            self.sent = True
            return b"partial"
        raise self.error


# -- protocol and default --------------------------------------------------------


def test_local_storage_implements_the_protocol(storage):
    assert isinstance(storage, FileStorageAdapter)


def test_an_object_missing_methods_is_not_an_adapter():
    class Partial:
        def create(self, file_id, data, meta): ...

    assert not isinstance(Partial(), FileStorageAdapter)


def test_the_default_is_local_storage_in_geenii_home(home):
    storage = default_file_storage()
    assert isinstance(storage, LocalFileStorage)
    assert storage.root == home / "files"


def test_the_default_root_follows_geenii_home(tmp_path, monkeypatch):
    storage = LocalFileStorage()
    monkeypatch.setenv("GEENII_HOME", str(tmp_path / "other"))
    assert storage.root == tmp_path / "other" / "files"


def test_root_may_be_a_string(root):
    assert LocalFileStorage(str(root)).root == root


# -- create ------------------------------------------------------------------------


def test_create_stores_bytes_and_metadata(storage, root):
    stored = storage.create(ID_A, io.BytesIO(b"hello"), meta_for(ID_A, name="a.txt"))

    assert stored == {"id": ID_A, "shared_with": [], "name": "a.txt"}
    assert (root / ID_A / "data").read_bytes() == b"hello"
    assert json.loads((root / ID_A / "meta.json").read_text(encoding="utf-8")) == stored
    assert entries(root) == [ID_A]  # no temp folder left


def test_create_makes_the_root_folder(storage, root):
    assert not root.exists()
    storage.create(ID_A, io.BytesIO(b""), meta_for(ID_A))
    assert storage.read_meta(ID_A)["id"] == ID_A


def test_create_calls_meta_after_reading_the_whole_stream(storage):
    stream = io.BytesIO(b"x" * (3 * 1024 * 1024 + 5))  # more than one chunk
    seen = []

    def meta():
        seen.append(stream.tell())
        return {"id": ID_A}

    storage.create(ID_A, stream, meta)
    assert seen == [3 * 1024 * 1024 + 5]


def test_create_keeps_non_ascii_metadata(storage):
    storage.create(ID_A, io.BytesIO(b""), meta_for(ID_A, name="résumé.txt"))
    assert storage.read_meta(ID_A)["name"] == "résumé.txt"


@pytest.mark.parametrize("error", [ValueError("too large"), OSError("connection lost"), KeyboardInterrupt()])
def test_a_failing_stream_leaves_nothing_behind(storage, root, error):
    with pytest.raises(type(error)):
        storage.create(ID_A, FailingStream(error), meta_for(ID_A))
    assert entries(root) == []
    with pytest.raises(FileNotFoundError):
        storage.read_meta(ID_A)


def test_a_failing_meta_callback_leaves_nothing_behind(storage, root):
    def meta():
        raise ValueError("bad metadata")

    with pytest.raises(ValueError, match="bad metadata"):
        storage.create(ID_A, io.BytesIO(b"data"), meta)
    assert entries(root) == []


def test_a_half_written_upload_is_invisible(storage, root):
    started, release = threading.Event(), threading.Event()

    def meta():
        started.set()
        release.wait(5)
        return {"id": ID_A}

    thread = threading.Thread(target=storage.create, args=(ID_A, io.BytesIO(b"data"), meta))
    thread.start()
    try:
        assert started.wait(5)
        assert list(storage.ids()) == []
        with pytest.raises(FileNotFoundError):
            storage.read_meta(ID_A)
        with pytest.raises(FileNotFoundError):
            storage.open(ID_A)
    finally:
        release.set()
        thread.join(5)
    assert list(storage.ids()) == [ID_A]


# -- reading -----------------------------------------------------------------------


def test_open_returns_the_bytes(storage):
    storage.create(ID_A, io.BytesIO(b"\x00\xffbinary"), meta_for(ID_A))
    with storage.open(ID_A) as f:
        assert f.read() == b"\x00\xffbinary"


def test_unknown_files_raise_file_not_found(storage):
    for call in (storage.read_meta, storage.open, storage.delete):
        with pytest.raises(FileNotFoundError):
            call(ID_A)
    with pytest.raises(FileNotFoundError):
        storage.update_meta(ID_A, lambda m: m)


def test_damaged_metadata_raises_value_error(storage, root):
    (root / ID_A).mkdir(parents=True)
    (root / ID_A / "meta.json").write_text("{broken")
    with pytest.raises(ValueError, match="damaged"):
        storage.read_meta(ID_A)


def test_a_folder_without_metadata_is_not_a_file(storage, root):
    (root / ID_A).mkdir(parents=True)
    (root / ID_A / "data").write_bytes(b"orphan")
    with pytest.raises(FileNotFoundError):
        storage.open(ID_A)


# -- update_meta --------------------------------------------------------------------


def test_update_meta_stores_the_change(storage):
    storage.create(ID_A, io.BytesIO(b""), meta_for(ID_A))
    stored = storage.update_meta(ID_A, lambda m: m | {"shared_with": ["bot"]})
    assert stored["shared_with"] == ["bot"]
    assert storage.read_meta(ID_A) == stored


def test_update_meta_with_none_changes_nothing(storage, root):
    storage.create(ID_A, io.BytesIO(b""), meta_for(ID_A))
    path = root / ID_A / "meta.json"
    before = path.stat().st_mtime_ns
    assert storage.update_meta(ID_A, lambda m: None) == {"id": ID_A, "shared_with": []}
    assert path.stat().st_mtime_ns == before


def test_update_meta_gives_change_a_copy(storage):
    storage.create(ID_A, io.BytesIO(b""), meta_for(ID_A))

    def change(meta):
        meta["shared_with"] = ["sneaky"]
        return None

    assert storage.update_meta(ID_A, change)["shared_with"] == []
    assert storage.read_meta(ID_A)["shared_with"] == []


def test_a_failing_change_keeps_the_metadata(storage):
    storage.create(ID_A, io.BytesIO(b""), meta_for(ID_A))

    def change(meta):
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        storage.update_meta(ID_A, change)
    assert storage.read_meta(ID_A) == {"id": ID_A, "shared_with": []}
    storage.update_meta(ID_A, lambda m: m | {"note": "ok"})  # the lock was released


def test_concurrent_updates_are_not_lost(storage):
    storage.create(ID_A, io.BytesIO(b""), meta_for(ID_A))

    def add(name):
        def change(meta):
            time.sleep(0.01)  # widen the read-modify-write window
            return meta | {"shared_with": meta["shared_with"] + [name]}

        storage.update_meta(ID_A, change)

    threads = [threading.Thread(target=add, args=(f"agent{i}",)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(10)
    assert sorted(storage.read_meta(ID_A)["shared_with"]) == sorted(f"agent{i}" for i in range(8))


def test_update_meta_does_not_touch_the_bytes(storage, root):
    storage.create(ID_A, io.BytesIO(b"content"), meta_for(ID_A))
    storage.update_meta(ID_A, lambda m: m | {"note": "x"})
    assert (root / ID_A / "data").read_bytes() == b"content"


# -- delete, ids, purge ----------------------------------------------------------------


def test_delete_removes_the_file_completely(storage, root):
    storage.create(ID_A, io.BytesIO(b"a"), meta_for(ID_A))
    storage.create(ID_B, io.BytesIO(b"b"), meta_for(ID_B))
    storage.delete(ID_A)
    assert entries(root) == [ID_B]  # no trash folder left
    with pytest.raises(FileNotFoundError):
        storage.read_meta(ID_A)
    with pytest.raises(FileNotFoundError):
        storage.delete(ID_A)


def test_ids_lists_only_complete_files(storage, root):
    assert list(storage.ids()) == []  # no root folder yet
    storage.create(ID_A, io.BytesIO(b"a"), meta_for(ID_A))
    storage.create(ID_B, io.BytesIO(b"b"), meta_for(ID_B))
    (root / f".tmp-{ID_A}x").mkdir()
    (root / f".trash-{ID_B}-1234").mkdir()
    (root / "stray.txt").write_text("not a folder")
    assert sorted(storage.ids()) == [ID_A, ID_B]


def _age(path, days):
    t = (datetime.now(UTC) - timedelta(days=days)).timestamp()
    os.utime(path, (t, t))


def test_purge_removes_only_old_leftovers(storage, root):
    storage.create(ID_A, io.BytesIO(b"a"), meta_for(ID_A))
    old_tmp, old_trash, new_tmp = root / ".tmp-f_old", root / ".trash-f_old-1", root / ".tmp-f_new"
    for folder in (old_tmp, old_trash, new_tmp):
        folder.mkdir()
        (folder / "data").write_bytes(b"x")
    _age(old_tmp, 3)
    _age(old_trash, 3)
    _age(root / ID_A, 3)  # an old but complete file is never purged

    storage.purge_incomplete(datetime.now(UTC) - timedelta(days=1))
    assert entries(root) == [".tmp-f_new", ID_A]


def test_purge_without_a_root_folder_does_nothing(storage, root):
    storage.purge_incomplete(datetime.now(UTC))
    assert not root.exists()
