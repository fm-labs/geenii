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
def procs_dir(tmp_path):
    return str(tmp_path / "processes")


async def _wait_done(pm: ProcessManager, pid: str, timeout: float = 5.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        info = await pm.status(pid)
        if info.state not in (ProcessState.PENDING, ProcessState.RUNNING):
            return info
        await asyncio.sleep(0.05)
    raise AssertionError(f"process {pid} did not finish")


async def _read_pidfile(path, timeout: float = 3.0) -> int:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists() and path.read_text().strip():
            return int(path.read_text().strip())
        await asyncio.sleep(0.05)
    raise AssertionError(f"{path} was not written")


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _assert_dead(pid: int, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _pid_alive(pid):
            return
        time.sleep(0.05)
    raise AssertionError(f"pid {pid} is still alive")


def test_list_command_runs_without_shell(procs_dir):
    async def main():
        pm = ProcessManager(procs_dir)
        info = await pm.start(["echo", "hello", "$HOME", "a;b"])
        assert info.shell is False
        assert (await _wait_done(pm, info.pid)).state == ProcessState.COMPLETED
        # No shell: variables are not expanded and ';' is a literal argument
        assert await pm.output(info.pid) == "hello $HOME a;b\n"

    asyncio.run(main())


def test_string_command_runs_through_shell(procs_dir):
    async def main():
        pm = ProcessManager(procs_dir)
        info = await pm.start("echo one && echo two | tr a-z A-Z")
        assert info.shell is True
        assert (await _wait_done(pm, info.pid)).state == ProcessState.COMPLETED
        assert await pm.output(info.pid) == "one\nTWO\n"

    asyncio.run(main())


def test_output_is_written_verbatim(procs_dir):
    async def main():
        pm = ProcessManager(procs_dir)
        info = await pm.start(["printf", "trailing  \\r\\nno-newline"])
        await _wait_done(pm, info.pid)
        with open(info.stdout_path, "rb") as f:
            assert f.read() == b"trailing  \r\nno-newline"

    asyncio.run(main())


def test_failed_and_stderr(procs_dir):
    async def main():
        pm = ProcessManager(procs_dir)
        info = await pm.start("echo oops >&2; exit 3")
        done = await _wait_done(pm, info.pid)
        assert (done.state, done.exit_code) == (ProcessState.FAILED, 3)
        assert await pm.output(info.pid, stream="stderr") == "oops\n"

    asyncio.run(main())


def test_output_tail(procs_dir):
    async def main():
        pm = ProcessManager(procs_dir)
        info = await pm.start(["sh", "-c", "for i in 1 2 3 4 5; do echo $i; done"])
        await _wait_done(pm, info.pid)
        assert await pm.output(info.pid, tail=2) == "4\n5"

    asyncio.run(main())


def test_output_offset_limit(procs_dir):
    async def main():
        pm = ProcessManager(procs_dir)
        info = await pm.start(["printf", "0123456789"])
        await _wait_done(pm, info.pid)
        assert await pm.output(info.pid, offset=3, limit=4) == "3456"
        assert await pm.output(info.pid, offset=7) == "789"
        assert await pm.output(info.pid, limit=2) == "01"
        assert await pm.output(info.pid, offset=10, limit=4) == ""
        assert await pm.output(info.pid, offset=99) == ""

    asyncio.run(main())


@pytest.mark.parametrize("limit", [4, 5, 7, 64])
def test_output_chunks_reassemble_multibyte_text(procs_dir, limit):
    text = "a€b😀cdé\nümlaut ✓ ok\n" * 3

    async def main():
        pm = ProcessManager(procs_dir)
        info = await pm.start(["printf", "%s", text])
        await _wait_done(pm, info.pid)
        chunks, offset = [], 0
        while chunk := await pm.output(info.pid, offset=offset, limit=limit):
            assert "�" not in chunk
            chunks.append(chunk)
            offset += limit
        assert "".join(chunks) == text

    asyncio.run(main())


def test_output_rejects_bad_ranges(procs_dir):
    async def main():
        pm = ProcessManager(procs_dir)
        info = await pm.start(["true"])
        await _wait_done(pm, info.pid)
        for kwargs in ({"tail": 2, "offset": 0}, {"tail": 2, "limit": 5},
                       {"offset": -1}, {"limit": 0}):
            with pytest.raises(ValueError):
                await pm.output(info.pid, **kwargs)

    asyncio.run(main())


def test_output_while_running(procs_dir):
    async def main():
        pm = ProcessManager(procs_dir)
        info = await pm.start("echo early; sleep 30")
        deadline = time.time() + 3
        while time.time() < deadline and await pm.output(info.pid) != "early\n":
            await asyncio.sleep(0.05)
        assert await pm.output(info.pid) == "early\n"
        assert (await pm.status(info.pid)).state == ProcessState.RUNNING
        await pm.kill(info.pid)

    asyncio.run(main())


def test_kill_reaches_the_whole_process_group(procs_dir, tmp_path):
    pidfile = tmp_path / "child.pid"

    async def main():
        pm = ProcessManager(procs_dir)
        info = await pm.start(f"sleep 30 & echo $! > {pidfile}; wait")
        grandchild = await _read_pidfile(pidfile)
        t0 = time.time()
        result = await pm.kill(info.pid)
        assert time.time() - t0 < 3
        assert result.state == ProcessState.KILLED  # kill() waits for the final state
        _assert_dead(grandchild)
        assert (await pm.status(info.pid)).state == ProcessState.KILLED

    asyncio.run(main())


def test_kill_waits_at_most_kill_wait_s(procs_dir, monkeypatch):
    monkeypatch.setattr(pm_mod, "KILL_WAIT_S", 0.3)

    async def main():
        pm = ProcessManager(procs_dir)
        info = await pm.start(["sh", "-c", "trap '' TERM; while :; do sleep 0.1; done"])
        await asyncio.sleep(0.2)
        t0 = time.time()
        result = await pm.kill(info.pid)
        assert time.time() - t0 < 2
        assert result.state == ProcessState.RUNNING  # ignored SIGTERM
        assert (await pm.kill(info.pid, force=True)).state == ProcessState.KILLED

    asyncio.run(main())


@pytest.mark.parametrize("bad", ["../escape", "..", ".hidden", "a/b", "x" * 65, "a b"])
def test_invalid_process_ids_are_rejected(procs_dir, tmp_path, bad):
    async def main():
        pm = ProcessManager(procs_dir)
        with pytest.raises(ValueError):
            await pm.start(["true"], pid=bad)
        for call in (pm.status, pm.output, pm.kill, pm.cleanup):
            with pytest.raises(ValueError):
                await call(bad)

    asyncio.run(main())
    assert not (tmp_path / "escape").exists()


def test_empty_process_id_means_auto_generate(procs_dir):
    async def main():
        pm = ProcessManager(procs_dir)
        info = await pm.start(["true"], pid="")
        assert len(info.pid) == 12
        with pytest.raises(ValueError):
            await pm.status("")
        await _wait_done(pm, info.pid)

    asyncio.run(main())


def test_duplicate_process_id_is_rejected(procs_dir):
    async def main():
        pm = ProcessManager(procs_dir)
        info = await pm.start(["true"], pid="job-1")
        await _wait_done(pm, info.pid)
        with pytest.raises(ValueError, match="already in use"):
            await pm.start(["true"], pid="job-1")

    asyncio.run(main())


def test_concurrent_starts_with_same_id(procs_dir):
    async def main():
        pm = ProcessManager(procs_dir)
        results = await asyncio.gather(*(pm.start(["sleep", "1"], pid="same") for _ in range(5)),
                                       return_exceptions=True)
        started = [r for r in results if not isinstance(r, Exception)]
        assert len(started) == 1
        assert all(isinstance(r, ValueError) for r in results if r not in started)
        await pm.shutdown()

    asyncio.run(main())


def test_failed_spawn_leaves_no_directory(procs_dir, tmp_path):
    async def main():
        pm = ProcessManager(procs_dir)
        with pytest.raises(FileNotFoundError):
            await pm.start(["true"], pid="nocwd", cwd=str(tmp_path / "missing"))
        with pytest.raises(KeyError):
            await pm.status("nocwd")
        # The ID is free again
        info = await pm.start(["true"], pid="nocwd")
        await _wait_done(pm, info.pid)

    asyncio.run(main())


def test_unknown_id_does_not_create_directories(procs_dir):
    async def main():
        pm = ProcessManager(procs_dir)
        with pytest.raises(KeyError):
            await pm.status("nope")
        with pytest.raises(KeyError):
            await pm.output("nope")
        with pytest.raises(KeyError):
            await pm.kill("nope")

    asyncio.run(main())
    assert not os.path.exists(os.path.join(procs_dir, "nope"))


def test_invalid_command_is_rejected(procs_dir):
    async def main():
        pm = ProcessManager(procs_dir)
        for bad in ("", "   ", [], ["ok", 1]):
            with pytest.raises(ValueError):
                await pm.start(bad)

    asyncio.run(main())


def test_list_includes_running_and_finished(procs_dir):
    async def main():
        pm = ProcessManager(procs_dir)
        done = await pm.start(["true"], pid="done")
        await _wait_done(pm, done.pid)
        running = await pm.start(["sleep", "30"], pid="running")
        assert [i.pid for i in await pm.list()] == ["running"]
        all_procs = {i.pid: i.state for i in await pm.list(include_finished=True)}
        assert all_procs == {"running": ProcessState.RUNNING, "done": ProcessState.COMPLETED}
        await pm.kill(running.pid)

    asyncio.run(main())


def test_restart_marks_leftover_running_processes_as_orphaned(tmp_path):
    procs_dir = tmp_path / "processes"
    stale = procs_dir / "stale"
    stale.mkdir(parents=True)
    (stale / "meta.json").write_text(json.dumps({
        "pid": "stale", "system_pid": 999999, "cmd": "sleep 100", "state": "running",
        "cwd": None, "started_at": time.time(),
    }))

    async def main():
        pm = ProcessManager(str(procs_dir))
        # Creating a manager leaves the records alone; recover() marks them
        assert (await pm.status("stale")).state == ProcessState.RUNNING
        assert pm.recover() == ["stale"]
        return await pm.status("stale")

    info = asyncio.run(main())
    assert info.state == ProcessState.ORPHANED
    assert info.error


def test_shutdown_terminates_running_processes(procs_dir, tmp_path, monkeypatch):
    monkeypatch.setattr(pm_mod, "TERMINATE_GRACE_S", 1.0)
    pidfile = tmp_path / "child.pid"

    async def main():
        pm = ProcessManager(procs_dir)
        a = await pm.start(["sleep", "30"])
        b = await pm.start(f"sleep 30 & echo $! > {pidfile}; wait")
        grandchild = await _read_pidfile(pidfile)
        await pm.shutdown()
        for info in (a, b):
            assert (await pm.status(info.pid)).state == ProcessState.KILLED
            _assert_dead(info.system_pid)
        _assert_dead(grandchild)
        assert await pm.list() == []

    asyncio.run(main())


def test_cleanup_refuses_running_process(procs_dir):
    async def main():
        pm = ProcessManager(procs_dir)
        info = await pm.start(["sleep", "30"])
        with pytest.raises(RuntimeError):
            await pm.cleanup(info.pid)
        await pm.kill(info.pid, force=True)
        await pm.cleanup(info.pid)
        with pytest.raises(KeyError):
            await pm.status(info.pid)

    asyncio.run(main())


def test_wait_returns_final_state(procs_dir):
    async def main():
        pm = ProcessManager(procs_dir)
        info = await pm.start("sleep 0.3; exit 2")
        done = await pm.wait(info.pid)
        assert (done.state, done.exit_code) == (ProcessState.FAILED, 2)
        # Already finished (and no longer in memory): answered from disk
        assert (await pm.wait(info.pid)).exit_code == 2

    asyncio.run(main())


def test_wait_timeout_and_cancel_leave_the_process_running(procs_dir):
    async def main():
        pm = ProcessManager(procs_dir)
        info = await pm.start(["sleep", "30"])
        with pytest.raises(asyncio.TimeoutError):
            await pm.wait(info.pid, timeout=0.2)
        waiter = asyncio.create_task(pm.wait(info.pid))
        await asyncio.sleep(0.1)
        waiter.cancel()
        assert (await pm.status(info.pid)).state == ProcessState.RUNNING
        await pm.kill(info.pid)
        assert (await pm.wait(info.pid)).state == ProcessState.KILLED

    asyncio.run(main())


@pytest.fixture
def short_dir():
    # Unix socket paths are limited to ~104 bytes on macOS; pytest's tmp_path is often longer
    d = tempfile.mkdtemp(prefix="pm", dir="/tmp" if os.path.isdir("/tmp") else None)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def test_service_and_client_roundtrip(short_dir):
    socket_path = os.path.join(short_dir, "pm.sock")
    service = ProcessManagerService(socket_path, pm=ProcessManager(os.path.join(short_dir, "procs")))

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
        long_proc = client.start(["sleep", "30"])
        assert (shell_proc["shell"], list_proc["shell"]) == (True, False)

        deadline = time.time() + 5
        while time.time() < deadline and client.status(list_proc["pid"])["state"] == "running":
            time.sleep(0.05)
        assert client.output(shell_proc["pid"]) == "HI\n"
        assert client.output(list_proc["pid"]) == "a b\n"
        assert {p["pid"] for p in client.list(include_finished=True)} >= {
            shell_proc["pid"], list_proc["pid"], long_proc["pid"]}

        with pytest.raises(RuntimeError, match="Invalid process ID"):
            client.start(["true"], pid="../x")
    finally:
        asyncio.run_coroutine_threadsafe(service.stop(), loop).result(10)
        loop.call_soon_threadsafe(loop.stop)
        thread.join(5)

    # stop() terminated the still-running process and recorded it
    _assert_dead(long_proc["system_pid"])
    with open(os.path.join(short_dir, "procs", long_proc["pid"], "meta.json")) as f:
        assert json.load(f)["state"] == "killed"
    assert not os.path.exists(socket_path)
