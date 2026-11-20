"""The shared file store (geenii.ibc.filestore, geenii.storage.filestorage): storage, the agent tools, mail attachments, the worker and the CLI."""

import hashlib
import io
import json
import os
from datetime import timedelta

import pytest
from click.testing import CliRunner

import geenii.g
from geenii import config, worker
from geenii.agent import tasks as tasks_mod
from geenii.agent import base_agent as base_agent_mod
from geenii.agent.registry import AgentRegistry, AgentSpec
from geenii.cli.worker_cli import worker as worker_cli
from geenii.hitl import PolicyHumanInTheLoopController
from geenii.ibc import filestore as files_mod
from geenii.ibc.comms import Mailbox, comms_tools, format_inbox
from geenii.storage.filestorage import FileStorageAdapter, LocalFileStorage, default_file_storage
from geenii.ibc.filestore import (
    MAX_FILE_SIZE,
    FileStore,
    attached_to_pending_mail,
    clean_name,
)
from geenii.ibc.tools import FILE_TOOL_NAMES, files_tools
from geenii.tool.common import ToolCallContext
from geenii.tool.registry import ToolRegistry


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    path = tmp_path / "geenii-home"
    monkeypatch.setenv("GEENII_HOME", str(path))
    monkeypatch.setattr(config, "read_user_settings", lambda: {})  # no allowed_dirs from the real settings
    return path


@pytest.fixture(autouse=True)
def registry(monkeypatch):
    reg = AgentRegistry()
    reg.configs["bot"] = AgentSpec(name="bot", model="fake:test")
    reg.configs["other"] = AgentSpec(name="other", model="fake:test")
    monkeypatch.setattr(geenii.g, "get_agent_registry", lambda: reg)
    return reg


@pytest.fixture
def store():
    return FileStore()


@pytest.fixture
def workdir(tmp_path):
    path = tmp_path / "work"
    path.mkdir()
    return path


# -- storage ---------------------------------------------------------------------


def test_put_copies_the_file_and_writes_metadata(store, workdir, home):
    src = workdir / "report.md"
    src.write_text("# Report\n")
    meta = store.put("bot", src, note="monthly")

    assert files_mod.FILE_ID_RE.fullmatch(meta["id"])
    assert meta | {"id": "x", "created_at": "x"} == {
        "id": "x", "name": "report.md", "size": 9, "mime": "text/markdown", "owner": "bot", "created_at": "x",
        "shared_with": [], "note": "monthly", "sha256": hashlib.sha256(b"# Report\n").hexdigest(),
    }
    folder = home / "files" / meta["id"]
    assert (folder / "data").read_text() == "# Report\n"
    assert json.loads((folder / "meta.json").read_text()) == meta
    assert store.info(meta["id"]) == meta
    # no temp folders left behind
    assert [p.name for p in (home / "files").iterdir()] == [meta["id"]]


def test_the_stored_copy_does_not_change_with_the_source(store, workdir):
    src = workdir / "a.txt"
    src.write_text("v1")
    meta = store.put("bot", src)
    src.write_text("v2")
    assert store.read_bytes(meta["id"]) == b"v1"


def test_put_text_and_read_text(store):
    meta = store.put_text("bot", "notes.txt", "héllo")
    assert meta["size"] == len("héllo".encode())
    assert store.read_text(meta["id"]) == ("héllo", False)


def test_read_text_truncates_long_files(store):
    meta = store.put_text("bot", "long.txt", "x" * 50)
    assert store.read_text(meta["id"], limit=10) == ("x" * 10, True)


def test_read_text_rejects_binary_files(store):
    meta = store.put_bytes("bot", b"\x89PNG\r\n\x1a\n\xff\xfe", "img.png")
    assert meta["mime"] == "image/png"
    with pytest.raises(ValueError, match="not a text file"):
        store.read_text(meta["id"])


def test_put_rejects_files_over_the_size_limit(store, monkeypatch, home, workdir):
    monkeypatch.setattr(files_mod, "MAX_FILE_SIZE", 10)
    with pytest.raises(ValueError, match="too large"):
        store.put_text("bot", "big.txt", "x" * 11)
    (workdir / "big.txt").write_text("x" * 11)
    with pytest.raises(ValueError, match="too large"):
        store.put("bot", workdir / "big.txt")  # streamed: stops while copying
    assert not any((home / "files").iterdir())  # the temp folder was removed
    assert MAX_FILE_SIZE == 25 * 1024 * 1024


class MemoryStorage:
    """A minimal FileStorageAdapter that keeps everything in dicts, to show FileStore only needs the protocol."""

    def __init__(self):
        self.data, self.meta = {}, {}

    def create(self, file_id, data, meta):
        content = data.read()
        stored = meta()
        self.data[file_id], self.meta[file_id] = content, stored
        return stored

    def read_meta(self, file_id):
        if file_id not in self.meta:
            raise FileNotFoundError(file_id)
        return dict(self.meta[file_id])

    def update_meta(self, file_id, change):
        changed = change(self.read_meta(file_id))
        if changed is not None:
            self.meta[file_id] = changed
        return self.read_meta(file_id)

    def open(self, file_id):
        self.read_meta(file_id)
        return io.BytesIO(self.data[file_id])

    def delete(self, file_id):
        self.read_meta(file_id)
        del self.data[file_id], self.meta[file_id]

    def ids(self):
        return iter(list(self.meta))

    def purge_incomplete(self, before):
        pass


def test_the_default_storage_is_local_in_geenii_home(home):
    storage = default_file_storage()
    assert isinstance(storage, LocalFileStorage) and isinstance(storage, FileStorageAdapter)
    assert storage.root == home / "files"
    assert isinstance(MemoryStorage(), FileStorageAdapter)


def test_root_is_a_local_storage_folder(tmp_path):
    store = FileStore(root=tmp_path / "elsewhere")
    meta = store.put_text("bot", "a.txt", "a")
    assert (tmp_path / "elsewhere" / meta["id"] / "data").read_text() == "a"
    with pytest.raises(ValueError, match="not both"):
        FileStore(root=tmp_path, storage=MemoryStorage())


def test_file_store_works_on_any_storage_adapter(home, workdir):
    storage = MemoryStorage()
    store = FileStore(storage=storage)
    meta = store.put_text("bot", "a.txt", "héllo", note="n")
    assert storage.data[meta["id"]] == "héllo".encode()
    assert meta["size"] == 6 and meta["sha256"] == hashlib.sha256("héllo".encode()).hexdigest()
    assert store.read_text(meta["id"]) == ("héllo", False)
    assert store.share(meta["id"], ["other"])["shared_with"] == ["other"]
    assert [m["id"] for m in store.list("other")] == [meta["id"]]
    assert store.copy_to(meta["id"], workdir).read_text() == "héllo"
    store.delete(meta["id"], by="bot")
    assert not store.exists(meta["id"]) and storage.data == {}
    assert not (home / "files").exists()  # nothing was written locally


def test_an_upload_over_the_limit_reaches_no_storage(monkeypatch):
    monkeypatch.setattr(files_mod, "MAX_FILE_SIZE", 10)
    storage = MemoryStorage()
    with pytest.raises(ValueError, match="too large"):
        FileStore(storage=storage)._store("bot", io.BytesIO(b"x" * 11), "a.txt", "")
    assert storage.meta == {}


@pytest.mark.parametrize(("name", "expected"), [
    ("../../etc/passwd", "passwd"),
    ("dir\\evil.txt", "evil.txt"),
    ("  a\nb.txt ", "ab.txt"),
])
def test_clean_name_keeps_only_a_safe_base_name(name, expected):
    assert clean_name(name) == expected


@pytest.mark.parametrize("name", ["", "..", "/", "   "])
def test_clean_name_rejects_empty_names(name):
    with pytest.raises(ValueError):
        clean_name(name)


def test_long_names_are_shortened_keeping_the_extension():
    name = clean_name("a" * 300 + ".txt")
    assert len(name) == files_mod.MAX_NAME and name.endswith(".txt")


@pytest.mark.parametrize("file_id", ["", "f_123", "../x", "f_" + "g" * 32, None])
def test_invalid_ids_are_rejected(store, file_id):
    with pytest.raises(ValueError, match="Invalid file id"):
        store.info(file_id)


def test_unknown_ids_are_a_value_error(store):
    with pytest.raises(ValueError, match="No file"):
        store.info("f_" + "0" * 32)
    assert not store.exists("f_" + "0" * 32)
    assert not store.exists("nonsense")


def test_owner_must_be_a_valid_agent_name(store):
    with pytest.raises(ValueError, match="Invalid agent name"):
        store.put_text("Bad Name", "a.txt", "x")


def test_list_is_newest_first_and_filters_by_filebox(store):
    a = store.put_text("bot", "a.txt", "a")
    b = store.put_text("other", "b.txt", "b")
    c = store.put_text("other", "c.txt", "c")
    store.share(c["id"], ["bot"])

    assert {m["id"] for m in store.list()} == {a["id"], b["id"], c["id"]}
    assert [m["id"] for m in store.list("bot")] == sorted([a["id"], c["id"]], key=lambda i: (
        store.info(i)["created_at"], i), reverse=True)
    assert {m["id"] for m in store.list("other")} == {b["id"], c["id"]}
    assert store.list("human") == []


def test_list_skips_damaged_files(store, home):
    good = store.put_text("bot", "a.txt", "a")
    bad = home / "files" / ("f_" + "1" * 32)
    bad.mkdir()
    (bad / "meta.json").write_text("{broken")
    assert [m["id"] for m in store.list()] == [good["id"]]


def test_share_adds_each_agent_once_and_never_the_owner(store):
    meta = store.put_text("bot", "a.txt", "a")
    store.share(meta["id"], ["other", "bot"])
    assert store.share(meta["id"], ["other", "human"])["shared_with"] == ["other", "human"]


def test_delete_is_for_the_owner_or_the_admin(store, home):
    meta = store.put_text("bot", "a.txt", "a")
    with pytest.raises(ValueError, match="Only the owner"):
        store.delete(meta["id"], by="other")
    store.delete(meta["id"], by="bot")
    assert not store.exists(meta["id"])
    assert list((home / "files").iterdir()) == []

    other = store.put_text("other", "b.txt", "b")
    store.delete(other["id"])  # admin
    with pytest.raises(ValueError, match="No file"):
        store.delete(other["id"])


def test_copy_to_a_folder_or_file_and_never_overwrites_by_default(store, workdir):
    meta = store.put_text("bot", "a.txt", "content")
    assert store.copy_to(meta["id"], workdir) == workdir / "a.txt"
    assert (workdir / "a.txt").read_text() == "content"
    with pytest.raises(ValueError, match="already exists"):
        store.copy_to(meta["id"], workdir / "a.txt")
    (workdir / "a.txt").write_text("mine")
    store.copy_to(meta["id"], workdir / "a.txt", overwrite=True)
    assert (workdir / "a.txt").read_text() == "content"
    assert store.copy_to(meta["id"], workdir / "sub" / "b.txt").read_text() == "content"


def test_gc_deletes_old_files_but_keeps_those_on_pending_mail(store, home):
    old = store.put_text("bot", "old.txt", "x")
    attached = store.put_text("bot", "attached.txt", "x")
    agentmail_read = store.put_text("bot", "read.txt", "x")
    Mailbox.send("bot", "other", "pending", "see file", attachments=[attached["id"]])
    sent = Mailbox.send("bot", "other", "done", "see file", attachments=[agentmail_read["id"]])
    Mailbox("other").read(sent["id"])
    leftover = home / "files" / ".tmp-f_leftover"
    leftover.mkdir()

    assert attached_to_pending_mail() == {attached["id"]}
    assert store.gc(timedelta(days=1)) == []  # nothing is old enough yet
    deleted = store.gc(timedelta(seconds=-1))  # everything counts as old
    assert set(deleted) == {old["id"], agentmail_read["id"]}
    assert [m["id"] for m in store.list()] == [attached["id"]]
    assert not leftover.exists()


def test_gc_keeps_files_attached_to_claimed_mail(store):
    meta = store.put_text("bot", "a.txt", "x")
    Mailbox.send("human", "bot", "s", "b", attachments=[meta["id"]])
    Mailbox("bot").claim_next(owner="host-1")
    assert store.gc(timedelta(seconds=-1)) == []


# -- mail attachments ------------------------------------------------------------


def test_send_with_attachments_shares_the_files(store):
    meta = store.put_text("bot", "a.txt", "hello")
    message = Mailbox.send("bot", "other", "file", "attached", attachments=[meta["id"], meta["id"]])
    assert message["attachments"] == [{"id": meta["id"], "name": "a.txt", "size": 5, "mime": "text/plain"}]
    assert store.info(meta["id"])["shared_with"] == ["other"]
    (header,) = Mailbox("other").list()
    assert header["attachments"] == 1
    assert format_inbox([header]).endswith("[1 file]")


def test_send_without_attachments_has_no_attachments_key():
    message = Mailbox.send("bot", "other", "s", "b")
    assert "attachments" not in message
    assert Mailbox("other").list()[0]["attachments"] == 0


def test_send_with_an_unknown_attachment_sends_and_shares_nothing(store):
    meta = store.put_text("bot", "a.txt", "x")
    with pytest.raises(ValueError, match="No file"):
        Mailbox.send("bot", "other", "s", "b", attachments=[meta["id"], "f_" + "0" * 32])
    assert Mailbox("other").list() == []
    assert store.info(meta["id"])["shared_with"] == []


def test_a_rejected_message_shares_nothing(store):
    meta = store.put_text("bot", "a.txt", "x")
    with pytest.raises(ValueError, match="Body"):
        Mailbox.send("bot", "other", "s", "", attachments=[meta["id"]])
    assert store.info(meta["id"])["shared_with"] == []


def test_send_rejects_too_many_attachments(store, monkeypatch):
    from geenii.ibc import comms

    monkeypatch.setattr(comms, "MAX_ATTACHMENTS", 1)
    ids = [store.put_text("bot", f"{i}.txt", "x")["id"] for i in range(2)]
    with pytest.raises(ValueError, match="Too many attachments"):
        Mailbox.send("bot", "other", "s", "b", attachments=ids)


def test_agentmail_send_tool_takes_attachments(store):
    meta = store.put_text("bot", "a.txt", "x")
    agentmail_send = {t.name: t for t in comms_tools("bot")}["agentmail_send"]
    assert agentmail_send.input_schema["properties"]["attachments"]["type"] == "array"
    result = agentmail_send.handler(to="other", subject="s", body="b", attachments=[meta["id"]])
    assert result["attachments"] == [meta["id"]]
    assert store.list("other")[0]["id"] == meta["id"]


# -- agent tools -----------------------------------------------------------------


def _tools(agent="bot"):
    return {t.name: t for t in files_tools(agent)}


def _invoke(tool, cwd, **args):
    result = tool.invoke(args, ctx=ToolCallContext(cwd=str(cwd)))
    return result


def test_files_tools_are_the_documented_set():
    assert set(_tools()) == FILE_TOOL_NAMES


def test_upload_and_download_between_agents(workdir, tmp_path, store):
    (workdir / "data.csv").write_text("a,b\n1,2\n")
    upload = _invoke(_tools("bot")["filestore_upload"], workdir, path="data.csv", note="numbers")
    assert not upload.is_error, upload.text
    file_id = upload.structured_content["id"]
    assert upload.structured_content["owner"] == "bot" and upload.structured_content["note"] == "numbers"

    other_dir = tmp_path / "other-work"
    other_dir.mkdir()
    download = _invoke(_tools("other")["filestore_download"], other_dir, file_id=file_id)
    assert not download.is_error, download.text
    assert (other_dir / "data.csv").read_text() == "a,b\n1,2\n"
    assert download.structured_content["saved"] == str((other_dir / "data.csv").resolve())

    again = _invoke(_tools("other")["filestore_download"], other_dir, file_id=file_id)
    assert again.is_error and "already exists" in again.text
    renamed = _invoke(_tools("other")["filestore_download"], other_dir, file_id=file_id, path="copy.csv")
    assert not renamed.is_error and (other_dir / "copy.csv").exists()


def test_upload_refuses_files_outside_the_allowed_folders(workdir, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_text("secret")
    result = _invoke(_tools()["filestore_upload"], workdir, path=str(outside))
    assert result.is_error and "not allowed" in result.text
    result = _invoke(_tools()["filestore_upload"], workdir, path="../outside.txt")
    assert result.is_error and "not allowed" in result.text


def test_upload_refuses_a_symlink_out_of_the_working_folder(workdir, tmp_path):
    (tmp_path / "outside.txt").write_text("secret")
    os.symlink(tmp_path / "outside.txt", workdir / "link.txt")
    result = _invoke(_tools()["filestore_upload"], workdir, path="link.txt")
    assert result.is_error and "not allowed" in result.text


def test_download_refuses_paths_outside_the_allowed_folders(workdir, tmp_path, store):
    meta = store.put_text("human", "a.txt", "x")
    result = _invoke(_tools()["filestore_download"], workdir, file_id=meta["id"], path="../escaped.txt")
    assert result.is_error and "not allowed" in result.text
    assert not (tmp_path / "escaped.txt").exists()


def test_save_text_read_text_info_and_list(workdir, store):
    tools = _tools("bot")
    saved = _invoke(tools["filestore_save_text"], workdir, name="summary.md", text="# Done")
    file_id = saved.structured_content["id"]
    read = _invoke(_tools("other")["filestore_read_text"], workdir, file_id=file_id)
    assert read.structured_content == {"id": file_id, "name": "summary.md", "text": "# Done"}

    info = _invoke(tools["filestore_info"], workdir, file_id=file_id).structured_content
    assert info["name"] == "summary.md" and info["sha256"] and info["shared_with"] == []

    shared = store.put_text("other", "for-bot.txt", "x")
    store.share(shared["id"], ["bot"])
    listing = _invoke(tools["filestore_list"], workdir).structured_content["files"]
    assert {(f["name"], f["shared"]) for f in listing} == {("summary.md", False), ("for-bot.txt", True)}
    empty = _invoke(_tools("human")["filestore_list"], workdir).structured_content
    assert empty == {"files": [], "note": "Your filebox is empty."}


def test_read_text_tool_says_when_it_is_truncated(workdir, store, monkeypatch):
    meta = store.put_text("bot", "long.txt", "x" * 30_000)
    result = _invoke(_tools()["filestore_read_text"], workdir, file_id=meta["id"]).structured_content
    assert len(result["text"]) == files_mod.MAX_TEXT and "truncated" in result


def test_tools_report_errors_instead_of_raising(workdir):
    result = _invoke(_tools()["filestore_info"], workdir, file_id="nope")
    assert result.is_error and "Invalid file id" in result.text


# -- init_agent registers the ibc tools the spec names -------------------------------


def test_init_agent_registers_named_file_and_mail_tools(monkeypatch, workdir):
    monkeypatch.setattr(geenii.g, "plugin_tools", ToolRegistry)
    spec = AgentSpec(name="bot", model="fake:test", tools=["filestore_upload", "agentmail_send", "read"],
                     working_dir=str(workdir))
    agent = geenii.g.init_agent(spec)
    names = agent._tool_registry.list_tool_names()
    assert {"filestore_upload", "agentmail_send", "read"} <= names
    assert not names & {"filestore_download", "agentmail_check_inbox"}


def test_init_agent_skips_ibc_tools_for_names_that_cant_own_files(monkeypatch, workdir):
    monkeypatch.setattr(geenii.g, "plugin_tools", ToolRegistry)
    spec = AgentSpec(name="Bad Name", model="fake:test", tools=["filestore_list"], working_dir=str(workdir))
    agent = geenii.g.init_agent(spec)
    assert not agent._tool_registry.has("filestore_list")


# -- worker: attachments reach the agent ---------------------------------------------


@pytest.fixture
def fake_model(tmp_path, monkeypatch):
    from geenii.provider.fake.provider import FakeProvider

    provider = FakeProvider()
    monkeypatch.setattr(tasks_mod, "generate_chat_completion",
                        lambda request, **kwargs: provider.generate_chat_completion(request))
    monkeypatch.setattr(base_agent_mod, "GEENII_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(geenii.g, "plugin_tools", ToolRegistry)
    return provider


def test_worker_lists_attachments_and_the_agent_can_read_them(fake_model, store, workdir):
    meta = store.put_text("human", "todo.txt", "buy milk")
    message = Mailbox.send("human", "bot", "todo", "what is on my list?", attachments=[meta["id"]])
    spec = AgentSpec(name="bot", model="fake:test", tools=["filestore_read_text"], working_dir=str(workdir))
    fake_model.enqueue_tool_call("filestore_read_text", {"file_id": meta["id"]})
    fake_model.enqueue("milk")

    answer = worker.handle(spec, message, None, PolicyHumanInTheLoopController.from_policy("filestore_read_text"))

    assert answer == "milk"
    prompt = [m.to_text() for m in fake_model.requests[0].messages if m.role == "user"][0]
    assert prompt.endswith(f"Attached files (in the shared file store; use filestore_read_text or filestore_download "
                           f"with the id):\n- todo.txt ({meta['id']}, 8 B)")
    tool_results = json.dumps([m.model_dump() if hasattr(m, "model_dump") else str(m)
                               for m in fake_model.requests[1].messages], default=str)
    assert "buy milk" in tool_results


# -- CLI -------------------------------------------------------------------------


def run(*args):
    return CliRunner().invoke(worker_cli, list(args), env={"COLUMNS": "200"})


def test_cli_put_list_info_get_rm(workdir, store):
    src = workdir / "plan.md"
    src.write_text("plan")
    result = run("files", "put", str(src), "--as", "human", "--note", "the plan", "--share", "bot")
    assert result.exit_code == 0, result.output
    file_id = result.output.strip()
    assert store.info(file_id)["shared_with"] == ["bot"]

    listing = run("files", "list", "bot")
    assert listing.exit_code == 0 and file_id in listing.output and "plan.md" in listing.output
    assert run("files", "list", "other").output.strip() == "The filebox of other is empty."

    info = run("files", "info", file_id)
    assert json.loads(info.output)["note"] == "the plan"

    out = workdir / "out"
    out.mkdir()
    assert run("files", "get", file_id, str(out)).exit_code == 0
    assert (out / "plan.md").read_text() == "plan"
    again = run("files", "get", file_id, str(out))
    assert again.exit_code != 0 and "already exists" in again.output
    assert run("files", "get", file_id, str(out), "--force").exit_code == 0

    assert run("files", "rm", file_id).exit_code == 0
    assert run("files", "list").output.strip() == "No files."
    bad = run("files", "info", file_id)
    assert bad.exit_code != 0 and "No file" in bad.output


def test_cli_send_attaches_ids_and_uploads_paths(workdir, store):
    stored = store.put_text("human", "a.txt", "a")
    src = workdir / "b.txt"
    src.write_text("b")
    result = run("send", "bot", "files", "see attached", "--attach", stored["id"], "-a", str(src))
    assert result.exit_code == 0, result.output
    assert "with 2 attachment(s)" in result.output
    (header,) = Mailbox("bot").list()
    message = Mailbox("bot").read(header["id"])
    assert [a["name"] for a in message["attachments"]] == ["a.txt", "b.txt"]
    assert {m["name"] for m in store.list("bot")} == {"a.txt", "b.txt"}

    shown = run("inbox", "bot", "--read", header["id"])
    assert "Attachments:\n- a.txt" in shown.output


def test_cli_send_checks_attachments_before_uploading(workdir, store):
    src = workdir / "b.txt"
    src.write_text("b")
    result = run("send", "bot", "s", "b", "-a", str(src), "-a", "missing.txt")
    assert result.exit_code != 0 and "neither a file id nor a file" in result.output
    assert store.list() == [] and Mailbox("bot").list() == []


def test_cli_gc(store):
    store.put_text("human", "a.txt", "a")
    assert run("files", "gc", "--older-than", "1").output.strip() == "Deleted 0 file(s)."
    assert run("files", "gc", "--older-than", "0").exit_code == 0
