import asyncio
import os
import re
import time

import pytest

from geenii import supervisor as sup_mod
from geenii.supervisor import LogBus, LogEvent, ProcConfig, Supervisor


@pytest.fixture(autouse=True)
def fast_backoff(monkeypatch):
    monkeypatch.setattr(sup_mod, "BACKOFF_INITIAL", 0.05)
    monkeypatch.setattr(sup_mod, "BACKOFF_MAX", 0.2)


def _restart_delays(sup: Supervisor, name: str) -> list[float]:
    return [float(m.group(1)) for line in sup.logs(name, 400) if (m := re.search(r"restarting in ([\d.]+)s", line))]


def test_backoff_escalates_on_repeated_crashes_and_is_capped():
    async def main():
        sup = Supervisor()
        # Log format rounds to 0.1s, so compare the stored backoff too
        await sup.ensure("crash", ProcConfig(name="crash", cmd=["sh", "-c", "exit 1"]))
        await asyncio.sleep(1.2)
        backoff = sup._backoff["crash"]
        delays = _restart_delays(sup, "crash")
        await sup.stop()
        return backoff, delays

    backoff, delays = asyncio.run(main())
    assert backoff == pytest.approx(0.2)
    assert len(delays) >= 4
    assert delays == sorted(delays)
    assert delays[-1] == pytest.approx(0.2)


def test_clean_exit_resets_backoff():
    async def main():
        sup = Supervisor()
        sup._backoff["ok"] = 0.2
        await sup.ensure("ok", ProcConfig(name="ok", cmd=["sh", "-c", "exit 0"]))
        await asyncio.sleep(0.3)
        backoff = sup._backoff["ok"]
        await sup.stop()
        return backoff

    assert asyncio.run(main()) == pytest.approx(0.05)


def test_restart_process_respawns_when_restart_disabled():
    async def main():
        sup = Supervisor()
        await sup.ensure("svc", ProcConfig(name="svc", cmd=["sleep", "30"], restart=False))
        await asyncio.sleep(0.2)
        first_pid = sup.status()["running"]["svc"]["pid"]
        await sup.restart_process("svc")
        await asyncio.sleep(0.2)
        running = sup.status()["running"]
        await sup.stop()
        return first_pid, running

    first_pid, running = asyncio.run(main())
    assert "svc" in running
    assert running["svc"]["pid"] != first_pid


def test_is_active_reflects_processes_and_watchers():
    async def main():
        sup = Supervisor()
        idle = sup.is_active()
        await sup.ensure("once", ProcConfig(name="once", cmd=["sh", "-c", "exit 0"], restart=False))
        while_running = sup.is_active()
        await asyncio.sleep(0.3)
        after_exit = sup.is_active()
        await sup.stop()
        return idle, while_running, after_exit

    assert asyncio.run(main()) == (False, True, False)


def test_run_log_buffers_are_bounded(monkeypatch):
    monkeypatch.setattr(sup_mod, "RUN_LOG_HISTORY", 2)

    async def main():
        sup = Supervisor()
        for i in range(3):
            result = await sup.run(["echo", str(i)], name=f"job{i}")
            assert result.stdout == [str(i)]
        return set(sup._logs)

    assert asyncio.run(main()) == {"job1", "job2"}


def test_logbus_subscriber_queue_drops_oldest(monkeypatch):
    monkeypatch.setattr(sup_mod, "SUBSCRIBER_QUEUE_SIZE", 3)

    async def main():
        bus = LogBus()
        q = bus.subscribe()
        for i in range(5):
            bus.append(LogEvent(t=0, name="p", tag="stdout", msg=str(i)))
        return [q.get_nowait().msg for _ in range(q.qsize())]

    assert asyncio.run(main()) == ["2", "3", "4"]


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


async def _read_pidfile(path, timeout=3.0) -> int:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if path.exists() and path.read_text().strip():
            return int(path.read_text().strip())
        await asyncio.sleep(0.05)
    raise AssertionError(f"{path} was not written")


def _grandchild_cmd(pidfile) -> list[str]:
    # The shell starts a background child and records its pid, so the tests can
    # check that the whole process group is signalled, not just the shell.
    return ["sh", "-c", f"sleep 30 & echo $! > {pidfile}; wait"]


def _assert_dead(pid: int, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not _pid_alive(pid):
            return
        time.sleep(0.05)
    raise AssertionError(f"pid {pid} is still alive")


def test_stop_kills_the_whole_process_group(tmp_path):
    pidfile = tmp_path / "pid"

    async def main():
        sup = Supervisor()
        await sup.ensure("grp", ProcConfig(name="grp", cmd=_grandchild_cmd(pidfile)))
        grandchild = await _read_pidfile(pidfile)
        await sup.stop()
        return grandchild

    _assert_dead(asyncio.run(main()))


def test_stop_process_and_restart_kill_the_whole_process_group(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"

    async def main():
        sup = Supervisor()
        await sup.ensure("grp", ProcConfig(name="grp", cmd=_grandchild_cmd(first)))
        before_restart = await _read_pidfile(first)
        # ensure() replaces the config without restarting; the restarted instance writes elsewhere
        await sup.ensure("grp", ProcConfig(name="grp", cmd=_grandchild_cmd(second)))
        await sup.restart_process("grp")
        after_restart = await _read_pidfile(second)
        await sup.stop_process("grp")
        return before_restart, after_restart

    before_restart, after_restart = asyncio.run(main())
    _assert_dead(before_restart)
    _assert_dead(after_restart)


def test_run_timeout_kills_the_whole_process_group(tmp_path):
    pidfile = tmp_path / "pid"

    async def main():
        sup = Supervisor()
        t0 = time.time()
        with pytest.raises(asyncio.TimeoutError):
            await sup.run(_grandchild_cmd(pidfile), name="slow", timeout=0.5)
        # A leaked child keeps the pipes open, and proc.wait() blocks until it exits
        assert time.time() - t0 < 5
        _assert_dead(await _read_pidfile(pidfile))

    asyncio.run(main())


def test_cancelled_run_kills_the_whole_process_group(tmp_path):
    pidfile = tmp_path / "pid"

    async def main():
        sup = Supervisor()
        task = asyncio.create_task(sup.run(_grandchild_cmd(pidfile), name="cancelled"))
        grandchild = await _read_pidfile(pidfile)
        t0 = time.time()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        # A leaked child keeps the pipes open, and proc.wait() blocks until it exits
        assert time.time() - t0 < 5
        _assert_dead(grandchild)

    asyncio.run(main())


def test_run_spawn_error_is_logged_and_raised(monkeypatch):
    monkeypatch.setattr(sup_mod, "RUN_LOG_HISTORY", 0)

    async def main():
        sup = Supervisor()
        with pytest.raises(FileNotFoundError):
            await sup.run(["/nonexistent/binary"], name="broken")
        return set(sup._logs)

    # The failed job's log buffer is retired like any finished run
    assert asyncio.run(main()) == set()


# -- services config file --------------------------------------------------------

import json

from geenii.supervisor import read_services


def _services_file(tmp_path, services):
    path = tmp_path / "services.json"
    path.write_text(json.dumps({"services": services}))
    return path


def test_read_services_parses_and_validates(tmp_path, monkeypatch):
    monkeypatch.setenv("SVC_PORT", "8123")
    path = _services_file(
        tmp_path,
        [
            {
                "name": "web",
                "cmd": ["python", "-m", "http.server", "$SVC_PORT"],
                "cwd": "~/site",
                "env": {"A": "1"},
            },
            {"name": "once", "cmd": ["true"], "restart": False},
            {"name": "off", "cmd": ["true"], "enabled": False},
            {"name": "web", "cmd": ["duplicate"]},
            {"name": "bad", "cmd": []},
            {"cmd": ["no-name"]},
        ],
    )
    services = read_services(path)
    assert [s.name for s in services] == ["web", "once"]
    web = services[0]
    assert web.cmd == ["python", "-m", "http.server", "8123"]
    assert web.cwd == os.path.expanduser("~/site")
    assert (web.env, web.restart, services[1].restart) == ({"A": "1"}, True, False)


def test_read_services_rejects_non_object(tmp_path):
    path = tmp_path / "services.json"
    path.write_text("[]")
    with pytest.raises(ValueError):
        read_services(path)


def test_apply_services(tmp_path):
    def svc(name, *cmd, **kw):
        return {"name": name, "cmd": list(cmd) or ["sleep", "30"], **kw}

    async def main():
        sup = Supervisor()
        await sup.ensure("adhoc", ProcConfig(name="adhoc", cmd=["sleep", "30"]))

        changes = await sup.apply_services(read_services(_services_file(tmp_path, [svc("a"), svc("b")])))
        assert changes == {"started": ["a", "b"], "stopped": [], "restarted": []}
        st = sup.status()
        assert {n: d["source"] for n, d in st["desired"].items()} == {
            "adhoc": "api",
            "a": "config",
            "b": "config",
        }
        await asyncio.sleep(0.2)
        pid_a = sup.status()["running"]["a"]["pid"]
        pid_b = sup.status()["running"]["b"]["pid"]

        # Unchanged file: nothing happens
        assert await sup.apply_services(read_services(_services_file(tmp_path, [svc("a"), svc("b")]))) == {
            "started": [],
            "stopped": [],
            "restarted": [],
        }

        # b stopped by hand is started again by a reload
        await sup.stop_process("b")
        changes = await sup.apply_services(read_services(_services_file(tmp_path, [svc("a"), svc("b")])))
        assert changes["started"] == ["b"]

        # a changed -> restarted with the new command; b removed -> stopped; c added
        new = [svc("a", "sleep", "31"), svc("c")]
        changes = await sup.apply_services(read_services(_services_file(tmp_path, new)))
        assert changes == {"started": ["c"], "stopped": ["b"], "restarted": ["a"]}
        await asyncio.sleep(0.2)
        st = sup.status()
        assert set(st["desired"]) == {"adhoc", "a", "c"}  # ad-hoc service untouched
        assert st["desired"]["a"]["cmd"] == ["sleep", "31"]
        assert st["running"]["a"]["pid"] != pid_a
        assert not _pid_alive(pid_a) and not _pid_alive(pid_b)
        await sup.stop()

    asyncio.run(main())


def test_apply_services_adopts_an_ad_hoc_service_of_the_same_name(tmp_path):
    async def main():
        sup = Supervisor()
        await sup.ensure("web", ProcConfig(name="web", cmd=["sleep", "30"]))
        changes = await sup.apply_services(
            read_services(_services_file(tmp_path, [{"name": "web", "cmd": ["sleep", "31"]}]))
        )
        st = sup.status()
        await sup.stop()
        return changes, st

    changes, st = asyncio.run(main())
    assert changes["restarted"] == ["web"]
    assert (st["desired"]["web"]["source"], st["desired"]["web"]["cmd"]) == (
        "config",
        ["sleep", "31"],
    )


def test_fast_exit_is_handled_before_respawn():
    """A process that exits before the watcher waits for it still gets its exit handled (and backoff)."""

    async def main():
        sup = Supervisor()
        # Several services started back to back: the loop is busy while "fast" exits
        await sup.ensure("fast", ProcConfig(name="fast", cmd=["true"]))
        for i in range(5):
            await sup.ensure(f"other{i}", ProcConfig(name=f"other{i}", cmd=["sleep", "30"]))
        await asyncio.sleep(0.6)
        await sup.stop()
        return sup.logs("fast", 400)

    lines = [line for line in asyncio.run(main()) if line.startswith("[supervisor] ")]
    starts = [i for i, line in enumerate(lines) if line.startswith("[supervisor] started pid=")]
    assert len(starts) >= 2
    for a, b in zip(starts, starts[1:]):
        assert any(line.startswith("[supervisor] exited rc=0") for line in lines[a:b]), lines[a:b]


def test_defaults(monkeypatch):
    monkeypatch.undo()  # the module's real values, not fast_backoff's
    assert sup_mod.BACKOFF_MAX == 3600.0
    assert sup_mod.MAX_FAILURES == 1000
    assert ProcConfig(name="x", cmd=["x"]).max_failures == 1000


def test_gives_up_after_max_failures_in_a_row_and_start_retries():
    async def main():
        sup = Supervisor()
        await sup.ensure("crash", ProcConfig(name="crash", cmd=["sh", "-c", "exit 1"], max_failures=3))
        await asyncio.sleep(1.0)
        desired = sup.status()["desired"]["crash"]
        starts = sum(1 for line in sup.logs("crash", 400) if "started pid=" in line)
        watcher_done = sup._watchers["crash"].done()
        # A manual restart resets the count and tries again
        await sup.restart_process("crash")
        after_restart = sup.status()["desired"]["crash"]
        await sup.stop()
        return desired, starts, watcher_done, after_restart

    desired, starts, watcher_done, after_restart = asyncio.run(main())
    assert starts == 3
    assert watcher_done
    assert desired["failures"] == 3 and desired["gave_up"]["failures"] == 3
    assert after_restart["gave_up"] is None and after_restart["failures"] == 0


def test_spawn_errors_count_towards_the_limit():
    async def main():
        sup = Supervisor()
        await sup.ensure("bad", ProcConfig(name="bad", cmd=["/nonexistent/binary"], max_failures=2))
        await asyncio.sleep(0.5)
        await sup.stop()
        return sup.status()["desired"]["bad"], sup.logs("bad", 50)

    desired, logs = asyncio.run(main())
    assert desired["gave_up"]["failures"] == 2
    assert sum("spawn error" in line for line in logs) == 2
    assert "retrying" not in [line for line in logs if "spawn error" in line][-1]


def test_healthy_run_resets_the_failure_count(monkeypatch):
    # Every run counts as long-lived, so failures never add up
    monkeypatch.setattr(sup_mod, "BACKOFF_RESET_AFTER", 0.0)

    async def main():
        sup = Supervisor()
        await sup.ensure("flaky", ProcConfig(name="flaky", cmd=["sh", "-c", "exit 1"], max_failures=2))
        await asyncio.sleep(0.6)
        status = sup.status()["desired"]["flaky"]
        await sup.stop()
        return status

    status = asyncio.run(main())
    assert status["gave_up"] is None
    assert status["failures"] == 1


def test_zero_max_failures_never_gives_up():
    async def main():
        sup = Supervisor()
        await sup.ensure("crash", ProcConfig(name="crash", cmd=["sh", "-c", "exit 1"], max_failures=0))
        await asyncio.sleep(0.8)
        status = sup.status()["desired"]["crash"]
        await sup.stop()
        return status

    status = asyncio.run(main())
    assert status["gave_up"] is None and status["failures"] >= 3


def test_read_services_max_failures(tmp_path):
    path = tmp_path / "services.json"
    path.write_text(
        '{"services": [{"name": "a", "cmd": ["x"], "max_failures": 7}, {"name": "b", "cmd": ["x"]}, '
        '{"name": "c", "cmd": ["x"], "max_failures": -1}]}'
    )
    services = {s.name: s for s in read_services(path)}
    assert services["a"].max_failures == 7
    assert services["b"].max_failures == 1000
    assert "c" not in services  # invalid entry is skipped
