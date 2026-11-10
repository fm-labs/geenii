import asyncio
import os
import shutil
import sys
import tempfile
import threading
import time

import pytest

from geenii.flow import Flow
from geenii.flow.processor import execute_pm_command
from geenii.pm.process_manager import ProcessManager
from geenii.pm.process_manager_client import ProcessManagerClient
from geenii.pm.process_manager_service import ProcessManagerService


@pytest.fixture
def daemon_socket():
    """A process manager daemon on its own event loop thread; yields its socket path."""
    # Unix socket paths are limited to ~104 bytes on macOS; pytest's tmp_path is often longer
    d = tempfile.mkdtemp(prefix="pmflow", dir="/tmp" if os.path.isdir("/tmp") else None)
    socket_path = os.path.join(d, "pm.sock")
    service = ProcessManagerService(socket_path, pm=ProcessManager(os.path.join(d, "procs")))
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
        yield socket_path
    finally:
        asyncio.run_coroutine_threadsafe(service.stop(), loop).result(10)
        loop.call_soon_threadsafe(loop.stop)
        thread.join(5)
        shutil.rmtree(d, ignore_errors=True)


def _step(socket_path, step_id="a", **config):
    return {
        "id": step_id,
        "processor": "execute_pm_command",
        "config": {"socket": socket_path, "poll_interval": 0.05, **config},
    }


def _run(*steps):
    events = []
    result = Flow("t", list(steps)).run(on_event=lambda e: events.append((e, time.monotonic())))
    return result, events


def test_waits_and_streams_output(daemon_socket):
    script = (
        "import sys, time; print('one', flush=True); time.sleep(0.3); "
        "print('err ✓', file=sys.stderr); print('two'); sys.stdout.write('no newline')"
    )
    result, events = _run(_step(daemon_socket, command=[sys.executable, "-c", script]))
    out = result.get("a").output
    assert result.get("a").status == "success"
    assert out["stdout"] == "one\ntwo\nno newline"
    assert out["stderr"] == "err ✓\n"
    assert (out["state"], out["rc"]) == ("completed", 0)
    assert len(out["process_id"]) == 12
    assert out["system_pid"] == ProcessManagerClient(daemon_socket).status(out["process_id"])["system_pid"] > 0

    streamed = [(e.type, e.data) for e, _ in events if e.type in ("stdout", "stderr")]
    assert [d for t, d in streamed if t == "stdout"] == ["one", "two", "no newline"]
    assert [d for t, d in streamed if t == "stderr"] == ["err ✓"]
    # the first line arrives while the process is still running
    first = next(t for e, t in events if e.data == "one")
    end = next(t for e, t in events if e.type == "step.end")
    assert end - first >= 0.2


def test_follows_output_across_chunks(daemon_socket, monkeypatch):
    monkeypatch.setattr(execute_pm_command, "CHUNK_SIZE", 16)
    expected = [f"line {i} é😀 " + "x" * (i % 23) for i in range(60)]
    script = (
        "import time\nfor i in range(60):\n"
        "    print(f'line {i} é😀 ' + 'x' * (i % 23), flush=True)\n"
        "    if i % 10 == 0: time.sleep(0.05)\n"
    )
    result, events = _run(_step(daemon_socket, command=[sys.executable, "-c", script]))
    assert result.get("a").output["stdout"] == "".join(line + "\n" for line in expected)
    assert [e.data for e, _ in events if e.type == "stdout"] == expected


def test_no_wait_returns_after_start(daemon_socket):
    started = time.monotonic()
    result, _ = _run(_step(daemon_socket, command=["sleep", "30"], pid="bg-sleep", wait=False))
    assert time.monotonic() - started < 3
    client = ProcessManagerClient(daemon_socket)
    status = client.status("bg-sleep")
    assert status["state"] == "running"
    assert result.get("a").output == {
        "process_id": "bg-sleep",
        "system_pid": status["system_pid"],
        "state": "running",
        "rc": None,
        "stdout": None,
        "stderr": None,
    }
    client.kill("bg-sleep")


def test_output_references_and_check(daemon_socket):
    result, _ = _run(
        _step(daemon_socket, "a", command="printf hello"),
        {
            **_step(daemon_socket, "b", command="echo ${a.stdout} | tr a-z A-Z"),
            "depends_on": "a",
        },
        _step(daemon_socket, "c", command="echo bad >&2; exit 3", check=True),
    )
    assert result.get("b").output["stdout"] == "HELLO\n"
    assert result.get("c").status == "failed"
    assert "failed with exit code 3: bad" in result.get("c").error


def test_timeout_kills_process(daemon_socket):
    started = time.monotonic()
    result, _ = _run(_step(daemon_socket, command=["sleep", "30"], pid="slow", timeout=0.3))
    assert result.get("a").status == "failed"
    assert "did not finish within 0.3s" in result.get("a").error
    assert time.monotonic() - started < 10
    assert ProcessManagerClient(daemon_socket).status("slow")["state"] == "killed"


def test_daemon_not_running(tmp_path):
    result, _ = _run(_step(str(tmp_path / "missing.sock"), command="true"))
    assert result.get("a").status == "failed"
