import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone

import pytest

from geenii import scheduler as sched_mod
from geenii.scheduler import ScheduledTask, Scheduler


@pytest.fixture(autouse=True)
def fast_terminate(monkeypatch):
    monkeypatch.setattr(sched_mod, "TERMINATE_GRACE_S", 1.0)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _wait_for_file(path, timeout=3.0) -> str:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists() and path.read_text().strip():
            return path.read_text().strip()
        time.sleep(0.05)
    raise AssertionError(f"{path} was not written")


def _spawn_grandchild_cmd(pidfile) -> list[str]:
    # The shell starts a background child and records its pid, so the test can
    # check that the whole process group is killed, not just the shell.
    return ["sh", "-c", f"sleep 30 & echo $! > {pidfile}; wait"]


def test_timeout_kills_command_and_its_children(tmp_path, caplog):
    pidfile = tmp_path / "pid"
    task = ScheduledTask(name="slow", interval="cron:* * * * *",
                         cmd=_spawn_grandchild_cmd(pidfile), timeout=0.5)
    task.load()

    t0 = time.time()
    with caplog.at_level(logging.ERROR, logger="geenii.scheduler"):
        asyncio.run(task.run())
    assert time.time() - t0 < 5
    assert "timed out" in caplog.text

    grandchild = int(_wait_for_file(pidfile))
    time.sleep(0.2)
    assert not _pid_alive(grandchild)


def test_stop_kills_running_command(tmp_path):
    pidfile = tmp_path / "pid"

    async def main():
        sched = Scheduler()
        await sched.add_task(ScheduledTask(name="long", interval="cron:* * * * *",
                                           cmd=_spawn_grandchild_cmd(pidfile)))
        await sched.start()
        await asyncio.sleep(0.05)  # let the main loop compute its initial schedule first
        sched._schedule["long"] = datetime.now(timezone.utc) - timedelta(seconds=1)
        grandchild = int(await asyncio.to_thread(_wait_for_file, pidfile))
        await sched.stop()
        await sched.wait_until_stopped()
        return grandchild

    grandchild = asyncio.run(main())
    time.sleep(0.2)
    assert not _pid_alive(grandchild)


def test_command_output_is_logged_per_line(caplog):
    task = ScheduledTask(name="echo", interval="cron:* * * * *",
                         cmd=["sh", "-c", "echo one; echo two; echo err >&2"])
    task.load()
    with caplog.at_level(logging.INFO, logger="geenii.scheduler"):
        asyncio.run(task.run())
    messages = [r.getMessage() for r in caplog.records]
    assert "Task 'echo' stdout: one" in messages
    assert "Task 'echo' stdout: two" in messages
    assert "Task 'echo' stderr: err" in messages


def test_callable_receives_params_and_env():
    calls = []

    def with_args(params, env=None):
        calls.append((params, env))

    def no_args():
        calls.append("no-args")

    t1 = ScheduledTask(name="a", interval="cron:* * * * *", run_fn=with_args,
                       params=["x", "y"], env={"K": "V"})
    t2 = ScheduledTask(name="b", interval="cron:* * * * *", run_fn=no_args, params=["ignored"])
    t1.load()
    t2.load()
    asyncio.run(t1.run())
    asyncio.run(t2.run())
    assert calls == [(["x", "y"], {"K": "V"}), "no-args"]


def test_callable_with_unsupported_signature_fails_to_load():
    def needs_three(a, b, c):
        pass

    task = ScheduledTask(name="bad", interval="cron:* * * * *", run_fn=needs_three)
    with pytest.raises(TypeError):
        task.load()


def test_duplicate_task_names_are_rejected(tmp_path):
    config = tmp_path / "scheduler.json"
    config.write_text(json.dumps({"tasks": [
        {"name": "dup", "interval": "cron:* * * * *", "cmd": ["true"]},
        {"name": "dup", "interval": "cron:*/5 * * * *", "cmd": ["false"]},
    ]}))
    sched = Scheduler()
    sched.load_config(config)
    assert [t.cmd for t in sched.tasks] == [["true"]]

    with pytest.raises(ValueError):
        asyncio.run(sched.add_task(ScheduledTask(name="dup", interval="cron:* * * * *", cmd=["true"])))


def test_config_fields_are_loaded(tmp_path):
    config = tmp_path / "scheduler.json"
    config.write_text(json.dumps({"tasks": [
        {"name": "t", "interval": "cron:* * * * *", "cmd": ["true"],
         "timeout": 12, "allow_overlap": True, "working_dir": str(tmp_path)},
    ]}))
    sched = Scheduler()
    sched.load_config(config)
    task = sched.tasks[0]
    assert (task.timeout, task.allow_overlap, str(task.working_dir)) == (12, True, str(tmp_path))


def test_overlapping_run_is_skipped(caplog):
    async def main():
        sched = Scheduler()
        await sched.add_task(ScheduledTask(name="busy", interval="cron:* * * * *", cmd=["sleep", "30"]))
        await sched.start()
        await asyncio.sleep(0.05)  # let the main loop compute its initial schedule first
        past = datetime.now(timezone.utc) - timedelta(seconds=1)
        sched._schedule["busy"] = past
        await asyncio.sleep(1.2)
        sched._schedule["busy"] = past
        await asyncio.sleep(1.2)
        launched = len(sched._running_tasks)
        await sched.stop()
        await sched.wait_until_stopped()
        return launched

    with caplog.at_level(logging.WARNING, logger="geenii.scheduler"):
        launched = asyncio.run(main())
    assert launched == 1
    assert "previous run is still in progress" in caplog.text


def test_scheduler_can_be_restarted():
    async def main():
        sched = Scheduler()
        await sched.start()
        await sched.stop()
        await sched.wait_until_stopped()
        await sched.start()
        running = sched.status["status"]
        await sched.stop()
        await sched.wait_until_stopped()
        return running

    assert asyncio.run(main()) == "running"
