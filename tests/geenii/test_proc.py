import asyncio
import os
import signal
import subprocess
import time

import pytest

from geenii import proc


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


def _grandchild_cmd(pidfile) -> list[str]:
    # The shell starts a background child and records its pid, so the tests can
    # check that the whole process group is signalled, not just the shell.
    return ["sh", "-c", f"sleep 30 & echo $! > {pidfile}; wait"]


async def _read_pidfile(path, timeout: float = 3.0) -> int:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists() and path.read_text().strip():
            return int(path.read_text().strip())
        await asyncio.sleep(0.05)
    raise AssertionError(f"{path} was not written")


def test_merged_env_overlays_without_mutating_os_environ(monkeypatch):
    monkeypatch.setenv("PROC_TEST_BASE", "base")
    env = proc.merged_env({"PROC_TEST_EXTRA": "x", "PROC_TEST_BASE": "override"})
    assert env["PROC_TEST_EXTRA"] == "x"
    assert env["PROC_TEST_BASE"] == "override"
    assert os.environ["PROC_TEST_BASE"] == "base"
    assert "PROC_TEST_EXTRA" not in os.environ
    assert proc.merged_env() == dict(os.environ)


def test_spawn_and_pump_lines(tmp_path):
    async def main():
        p = await proc.spawn(["sh", "-c", "echo $PROC_VAR; pwd; echo err >&2"],
                             env={"PROC_VAR": "hello"}, cwd=str(tmp_path))
        out, err = [], []
        await asyncio.gather(proc.pump_lines(p.stdout, out.append),
                             proc.pump_lines(p.stderr, err.append), p.wait())
        return p, out, err

    p, out, err = asyncio.run(main())
    assert p.returncode == 0
    assert out == ["hello", os.path.realpath(tmp_path)]
    assert err == ["err"]


@pytest.mark.skipif(not proc.USE_PROCESS_GROUPS, reason="needs process groups")
def test_spawn_starts_a_new_process_group():
    async def main():
        p = await proc.spawn(["sleep", "30"], capture_output=False)
        try:
            return p.pid, os.getpgid(p.pid)
        finally:
            await proc.terminate(p)

    pid, pgid = asyncio.run(main())
    assert pgid == pid != os.getpgid(0)


def test_terminate_kills_the_whole_process_group(tmp_path):
    pidfile = tmp_path / "pid"

    async def main():
        p = await proc.spawn(_grandchild_cmd(pidfile), capture_output=False)
        grandchild = await _read_pidfile(pidfile)
        t0 = time.time()
        rc = await proc.terminate(p, grace=1.0)
        assert time.time() - t0 < 3
        _assert_dead(grandchild)
        return rc

    assert asyncio.run(main()) == -signal.SIGTERM


def test_terminate_escalates_to_sigkill():
    async def main():
        # Ignores SIGTERM, so only the SIGKILL after the grace period stops it
        p = await proc.spawn(["sh", "-c", "trap '' TERM; while :; do sleep 0.1; done"], capture_output=False)
        await asyncio.sleep(0.2)
        t0 = time.time()
        rc = await proc.terminate(p, grace=0.5)
        return rc, time.time() - t0

    rc, elapsed = asyncio.run(main())
    assert rc == -proc.SIGKILL
    assert 0.4 < elapsed < 3


def test_terminate_on_exited_process_returns_exit_code():
    async def main():
        p = await proc.spawn(["sh", "-c", "exit 3"], capture_output=False)
        await p.wait()
        return await proc.terminate(p)

    assert asyncio.run(main()) == 3


def test_terminate_sync_kills_the_whole_process_group(tmp_path):
    pidfile = tmp_path / "pid"
    p = subprocess.Popen(_grandchild_cmd(pidfile), start_new_session=proc.USE_PROCESS_GROUPS)
    grandchild = asyncio.run(_read_pidfile(pidfile))
    assert proc.terminate_sync(p, grace=1.0) == -signal.SIGTERM
    _assert_dead(grandchild)
    assert proc.terminate_sync(p) == -signal.SIGTERM  # already exited: no-op


def test_signal_group_ignores_exited_process():
    p = subprocess.Popen(["true"], start_new_session=proc.USE_PROCESS_GROUPS)
    p.wait()
    proc.signal_group(p, signal.SIGTERM)  # must not raise


def test_add_shutdown_handlers_calls_back_on_signal():
    async def main():
        fired = asyncio.Event()
        proc.add_shutdown_handlers(fired.set, signals=(signal.SIGUSR1,))
        os.kill(os.getpid(), signal.SIGUSR1)
        await asyncio.wait_for(fired.wait(), timeout=2)
        asyncio.get_running_loop().remove_signal_handler(signal.SIGUSR1)
        return fired.is_set()

    assert asyncio.run(main())
