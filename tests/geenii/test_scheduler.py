import asyncio
import json
import logging
import os
import time
from datetime import UTC, datetime, timedelta

import pytest

from geenii import scheduler as sched_mod
from geenii.pm.process_manager import ProcessManager, ProcessState
from geenii.scheduler import ScheduledTask, Scheduler


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
    task = ScheduledTask(
        name="slow",
        interval="cron:* * * * *",
        cmd=_spawn_grandchild_cmd(pidfile),
        timeout=0.5,
    )
    task.load()

    t0 = time.time()
    with caplog.at_level(logging.ERROR, logger="geenii.scheduler"):
        asyncio.run(task.run(ProcessManager()))
    assert time.time() - t0 < 5
    assert "timed out" in caplog.text

    grandchild = int(_wait_for_file(pidfile))
    time.sleep(0.2)
    assert not _pid_alive(grandchild)


def test_stop_kills_running_command(tmp_path):
    pidfile = tmp_path / "pid"

    async def main():
        sched = Scheduler(ProcessManager(str(tmp_path / "procs")))
        await sched.add_task(
            ScheduledTask(
                name="long",
                interval="cron:* * * * *",
                cmd=_spawn_grandchild_cmd(pidfile),
            )
        )
        await sched.start()
        await asyncio.sleep(0.05)  # let the main loop compute its initial schedule first
        sched._schedule["long"] = datetime.now(UTC) - timedelta(seconds=1)
        grandchild = int(await asyncio.to_thread(_wait_for_file, pidfile))
        await sched.stop()
        await sched.wait_until_stopped()
        return grandchild

    grandchild = asyncio.run(main())
    time.sleep(0.2)
    assert not _pid_alive(grandchild)


def test_command_runs_as_process_manager_process(tmp_path):
    pm = ProcessManager(str(tmp_path / "procs"))
    task = ScheduledTask(
        name="echo task",
        interval="cron:* * * * *",
        cmd=["sh", "-c", "echo one; echo two; echo err >&2"],
    )
    task.load()
    asyncio.run(task.run(pm))

    run_id = task.last_run_id
    assert run_id and run_id.startswith("echo-task-")  # name sanitized for process IDs

    async def check():
        info = await pm.status(run_id)
        return info, await pm.output(run_id), await pm.output(run_id, stream="stderr")

    info, out, err = asyncio.run(check())
    assert (info.state, info.exit_code, info.cmd) == (
        ProcessState.COMPLETED,
        0,
        task.cmd,
    )
    assert (out, err) == ("one\ntwo\n", "err\n")


def test_failed_command_is_logged_with_run_id(tmp_path, caplog):
    task = ScheduledTask(name="fails", interval="cron:* * * * *", cmd=["sh", "-c", "exit 4"])
    task.load()
    with caplog.at_level(logging.ERROR, logger="geenii.scheduler"):
        asyncio.run(task.run(ProcessManager(str(tmp_path / "procs"))))
    assert "exited with code 4" in caplog.text
    assert f"geenii pm output {task.last_run_id}" in caplog.text


def test_cmd_task_requires_a_process_manager():
    task = ScheduledTask(name="t", interval="cron:* * * * *", cmd=["true"])
    task.load()
    with pytest.raises(ValueError, match="needs a ProcessManager"):
        asyncio.run(task.run())


def test_old_runs_are_pruned(tmp_path, monkeypatch):
    monkeypatch.setattr(sched_mod, "RUNS_KEPT_PER_TASK", 2)
    pm = ProcessManager(str(tmp_path / "procs"))
    task = ScheduledTask(name="tick", interval="cron:* * * * *", cmd=["true"])
    other = ScheduledTask(name="tick-other", interval="cron:* * * * *", cmd=["true"])
    task.load()
    other.load()

    async def main():
        ids = []
        await other.run(pm)
        for _ in range(4):
            await task.run(pm)
            ids.append(task.last_run_id)
            await asyncio.sleep(0.01)
        return ids, {p.pid for p in await pm.list(include_finished=True)}

    ids, remaining = asyncio.run(main())
    # Only the newest two runs of "tick" survive; the similarly named task is untouched
    assert remaining == {ids[-1], ids[-2], other.last_run_id}


def test_callable_receives_params_and_env():
    calls = []

    def with_args(params, env=None):
        calls.append((params, env))

    def no_args():
        calls.append("no-args")

    t1 = ScheduledTask(
        name="a",
        interval="cron:* * * * *",
        run_fn=with_args,
        params=["x", "y"],
        env={"K": "V"},
    )
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
    config.write_text(
        json.dumps(
            {
                "tasks": [
                    {"name": "dup", "interval": "cron:* * * * *", "cmd": ["true"]},
                    {"name": "dup", "interval": "cron:*/5 * * * *", "cmd": ["false"]},
                ]
            }
        )
    )
    sched = Scheduler()
    sched.load_config(config)
    assert [t.cmd for t in sched.tasks] == [["true"]]

    with pytest.raises(ValueError):
        asyncio.run(sched.add_task(ScheduledTask(name="dup", interval="cron:* * * * *", cmd=["true"])))


def test_config_fields_are_loaded(tmp_path):
    config = tmp_path / "scheduler.json"
    config.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "name": "t",
                        "interval": "cron:* * * * *",
                        "cmd": ["true"],
                        "timeout": 12,
                        "allow_overlap": True,
                        "working_dir": str(tmp_path),
                    },
                ]
            }
        )
    )
    sched = Scheduler()
    sched.load_config(config)
    task = sched.tasks[0]
    assert (task.timeout, task.allow_overlap, str(task.working_dir)) == (
        12,
        True,
        str(tmp_path),
    )


def test_overlapping_run_is_skipped(caplog):
    async def main():
        sched = Scheduler()
        await sched.add_task(ScheduledTask(name="busy", interval="cron:* * * * *", cmd=["sleep", "30"]))
        await sched.start()
        await asyncio.sleep(0.05)  # let the main loop compute its initial schedule first
        past = datetime.now(UTC) - timedelta(seconds=1)
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


def test_reload_config_while_running(tmp_path):
    config = tmp_path / "scheduler.json"

    def write(tasks):
        config.write_text(json.dumps({"tasks": tasks}))

    write(
        [
            {"name": "keep", "interval": "cron:0 0 1 1 *", "cmd": ["true"]},
            {"name": "retime", "interval": "cron:0 0 1 1 *", "cmd": ["true"]},
            {"name": "gone", "interval": "cron:0 0 1 1 *", "cmd": ["sleep", "30"]},
        ]
    )

    async def main():
        sched = Scheduler()
        sched.load_config(config)
        await sched.start()
        await asyncio.sleep(0.05)
        await sched.run_now("gone")  # a run in progress when its task is removed
        keep_next = sched._schedule["keep"]

        write(
            [
                {
                    "name": "keep",
                    "interval": "cron:0 0 1 1 *",
                    "cmd": ["true"],
                    "timeout": 5,
                },
                {"name": "retime", "interval": "cron:*/5 * * * *", "cmd": ["true"]},
                {"name": "new", "interval": "cron:0 0 1 1 *", "cmd": ["true"]},
            ]
        )
        changes = await sched.reload_config(config)
        state = {
            "names": [t.name for t in sched.tasks],
            "keep_unchanged": sched._schedule["keep"] == keep_next,
            "retime_rescheduled": sched._schedule["retime"] < keep_next,
            "gone_scheduled": "gone" in sched._schedule,
            "gone_still_running": sched._is_running("gone"),
            "keep_timeout": next(t for t in sched.tasks if t.name == "keep").timeout,
        }
        await sched.stop()
        await sched.wait_until_stopped()
        return changes, state

    changes, state = asyncio.run(main())
    assert changes == {
        "added": ["new"],
        "removed": ["gone"],
        "updated": ["keep", "retime"],
    }
    assert state == {
        "names": ["keep", "retime", "new"],
        "keep_unchanged": True,
        "retime_rescheduled": True,
        "gone_scheduled": False,
        "gone_still_running": True,
        "keep_timeout": 5,
    }


def test_reload_config_missing_file(tmp_path):
    with pytest.raises(FileNotFoundError):
        asyncio.run(Scheduler().reload_config(tmp_path / "missing.json"))
