import asyncio
import re

import pytest

from geenii import supervisor as sup_mod
from geenii.supervisor import LogBus, LogEvent, ProcConfig, Supervisor


@pytest.fixture(autouse=True)
def fast_backoff(monkeypatch):
    monkeypatch.setattr(sup_mod, "BACKOFF_INITIAL", 0.05)
    monkeypatch.setattr(sup_mod, "BACKOFF_MAX", 0.2)


def _restart_delays(sup: Supervisor, name: str) -> list[float]:
    return [float(m.group(1)) for line in sup.logs(name, 400)
            if (m := re.search(r"restarting in ([\d.]+)s", line))]


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
