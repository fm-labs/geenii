import asyncio
import json
import os
import shutil
import tempfile
import threading
import time

import pytest

from geenii.pm import process_manager as pm_mod
from geenii.pm.process_manager import ProcessManager, ProcessState
from geenii.pm.process_manager_client import ProcessManagerClient
from geenii.pm.process_manager_service import ProcessManagerService


@pytest.fixture
def pm(tmp_path):
    return ProcessManager(processes_dir=str(tmp_path / "processes"))


def _wait_done(pm: ProcessManager, pid: str, timeout: float = 5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        info = pm.status(pid)
        if info.state not in (ProcessState.PENDING, ProcessState.RUNNING):
            return info
        time.sleep(0.05)
    raise AssertionError(f"process {pid} did not finish")


def _wait_for_file(path, timeout=3.0) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists() and path.read_text().strip():
            return path.read_text().strip()
        time.sleep(0.05)
    raise AssertionError(f"{path} was not written")


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_list_command_runs_without_shell(pm):
    info = pm.start(["echo", "hello", "$HOME", "a;b"])
    assert info.shell is False
    assert _wait_done(pm, info.pid).state == ProcessState.COMPLETED
    # No shell: variables are not expanded and ';' is a literal argument
    assert pm.output(info.pid) == "hello $HOME a;b\n"


def test_string_command_runs_through_shell(pm):
    info = pm.start("echo one && echo two | tr a-z A-Z")
    assert info.shell is True
    assert _wait_done(pm, info.pid).state == ProcessState.COMPLETED
    assert pm.output(info.pid) == "one\nTWO\n"


def test_failed_and_stderr(pm):
    info = pm.start("echo oops >&2; exit 3")
    done = _wait_done(pm, info.pid)
    assert (done.state, done.exit_code) == (ProcessState.FAILED, 3)
    assert pm.output(info.pid, stream="stderr") == "oops\n"


def test_output_tail(pm):
    info = pm.start(["sh", "-c", "for i in 1 2 3 4 5; do echo $i; done"])
    _wait_done(pm, info.pid)
    assert pm.output(info.pid, tail=2) == "4\n5"


def test_kill_reaches_the_whole_process_group(pm, tmp_path):
    pidfile = tmp_path / "child.pid"
    info = pm.start(f"sleep 30 & echo $! > {pidfile}; wait")
    grandchild = int(_wait_for_file(pidfile))

    result = pm.kill(info.pid)
    assert result.state == ProcessState.KILLED  # kill() waits for the final state
    time.sleep(0.2)
    assert not _pid_alive(grandchild)
    assert pm.status(info.pid).state == ProcessState.KILLED


@pytest.mark.parametrize("bad", ["../escape", "..", ".hidden", "a/b", "x" * 65, "a b"])
def test_invalid_process_ids_are_rejected(pm, tmp_path, bad):
    with pytest.raises(ValueError):
        pm.start(["true"], pid=bad)
    for call in (pm.status, pm.output, pm.kill, pm.cleanup):
        with pytest.raises(ValueError):
            call(bad)
    assert not (tmp_path / "escape").exists()


def test_empty_process_id_means_auto_generate(pm):
    info = pm.start(["true"], pid="")
    assert len(info.pid) == 12
    with pytest.raises(ValueError):
        pm.status("")


def test_duplicate_process_id_is_rejected(pm):
    info = pm.start(["true"], pid="job-1")
    _wait_done(pm, info.pid)
    with pytest.raises(ValueError, match="already in use"):
        pm.start(["true"], pid="job-1")


def test_unknown_id_does_not_create_directories(pm, tmp_path):
    with pytest.raises(KeyError):
        pm.status("nope")
    with pytest.raises(KeyError):
        pm.output("nope")
    assert not (tmp_path / "processes" / "nope").exists()


def test_invalid_command_is_rejected(pm):
    for bad in ("", "   ", [], ["ok", 1]):
        with pytest.raises(ValueError):
            pm.start(bad)


def test_restart_marks_leftover_running_processes_as_orphaned(tmp_path):
    procs_dir = tmp_path / "processes"
    stale = procs_dir / "stale"
    stale.mkdir(parents=True)
    (stale / "meta.json").write_text(json.dumps({
        "pid": "stale", "system_pid": 999999, "cmd": "sleep 100", "state": "running",
        "cwd": None, "started_at": time.time(),
    }))

    pm = ProcessManager(processes_dir=str(procs_dir))
    info = pm.status("stale")
    assert info.state == ProcessState.ORPHANED
    assert info.error


def test_shutdown_terminates_running_processes(pm, monkeypatch):
    monkeypatch.setattr(pm_mod, "TERMINATE_GRACE_S", 1.0)
    info = pm.start(["sleep", "30"])
    system_pid = info.system_pid
    pm.shutdown()
    assert pm.status(info.pid).state == ProcessState.KILLED
    assert not _pid_alive(system_pid)


def test_cleanup_refuses_running_process(pm):
    info = pm.start(["sleep", "30"])
    with pytest.raises(RuntimeError):
        pm.cleanup(info.pid)
    pm.kill(info.pid, force=True)
    pm.cleanup(info.pid)
    with pytest.raises(KeyError):
        pm.status(info.pid)


@pytest.fixture
def short_dir():
    # Unix socket paths are limited to ~104 bytes on macOS; pytest's tmp_path is often longer
    d = tempfile.mkdtemp(prefix="pm", dir="/tmp" if os.path.isdir("/tmp") else None)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_service_and_client_roundtrip(short_dir, monkeypatch):
    monkeypatch.setattr(pm_mod, "PROCESSES_DIR", os.path.join(short_dir, "procs"))
    socket_path = os.path.join(short_dir, "pm.sock")
    service = ProcessManagerService(socket_path)
    service._pm = ProcessManager(processes_dir=os.path.join(short_dir, "procs"))

    loop = asyncio.new_event_loop()
    started = threading.Event()

    def run():
        asyncio.set_event_loop(loop)
        loop.run_until_complete(service.start())
        started.set()
        loop.run_forever()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    assert started.wait(5)
    try:
        client = ProcessManagerClient(socket_path)
        assert client.is_available()

        shell_proc = client.start("echo hi | tr a-z A-Z")
        list_proc = client.start(["echo", "a b"])
        assert (shell_proc["shell"], list_proc["shell"]) == (True, False)

        deadline = time.time() + 5
        while time.time() < deadline and client.status(list_proc["pid"])["state"] == "running":
            time.sleep(0.05)
        assert client.output(shell_proc["pid"]) == "HI\n"
        assert client.output(list_proc["pid"]) == "a b\n"

        with pytest.raises(RuntimeError, match="Invalid process ID"):
            client.start(["true"], pid="../x")
    finally:
        asyncio.run_coroutine_threadsafe(service.stop(), loop).result(10)
        loop.call_soon_threadsafe(loop.stop)
        thread.join(5)
