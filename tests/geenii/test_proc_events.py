import asyncio
import csv
import io
import json
import os
import time
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from geenii import proc_events, proc_stats
from geenii import supervisor as sup_mod
from geenii.daemon.host import ProcessHost
from geenii.pm.process_manager import ProcessManager
from geenii.scheduler import ScheduledTask, Scheduler
from geenii.server.server import app
from geenii.supervisor import ProcConfig, Supervisor


def _events(**match):
    return [e for e in proc_events.read_events() if all(e.get(k) == v for k, v in match.items())]


def _wait_until(predicate, timeout=5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("condition not met in time")


# -- redaction ----------------------------------------------------------------


@pytest.mark.parametrize(
    ("cmd", "expected"),
    [
        (["curl", "-H", "Authorization: Bearer abc123"], ["curl", "-H", "Authorization: Bearer ***"]),
        (["tool", "--api-key", "sk-1", "--name", "x"], ["tool", "--api-key", "***", "--name", "x"]),
        (["env", "GITHUB_TOKEN=ghp_x", "PATH=/bin"], ["env", "GITHUB_TOKEN=***", "PATH=/bin"]),
        (["run", "--password=hunter2"], ["run", "--password=***"]),
        ("API_KEY=abc ./run.sh --verbose", "API_KEY=*** ./run.sh --verbose"),
        (None, None),
    ],
)
def test_redact_cmd(cmd, expected):
    assert proc_events.redact_cmd(cmd) == expected


def test_redact_shortens_long_commands():
    out = proc_events.redact_cmd(["x" * 500, *[str(i) for i in range(100)]])
    assert len(out[0]) == proc_events.MAX_ARG_LEN
    assert len(out) == proc_events.MAX_CMD_ARGS + 1
    assert out[-1].startswith("… (+")


# -- record / read --------------------------------------------------------------


def test_record_and_read(isolated_proc_events):
    proc_events.record("pm", "start", run_id="a", cmd=["echo", "TOKEN=x"], name=None)
    proc_events.record("supervisor", "service.stop", actor="api", name="web")
    files = os.listdir(isolated_proc_events)
    assert files == [f"proc-events-{datetime.now(UTC):%Y-%m}.log"]
    events = list(proc_events.read_events())
    assert [e["event"] for e in events] == ["start", "service.stop"]
    assert events[0]["cmd"] == ["echo", "TOKEN=***"]
    assert "name" not in events[0]  # None fields are left out
    assert events[0]["ts"].endswith("+00:00")


def test_record_never_raises(monkeypatch, isolated_proc_events):
    isolated_proc_events.parent.mkdir(parents=True)
    isolated_proc_events.write_text("a file where the log directory should be")
    proc_events.record("pm", "start")  # logged as a warning, not raised


def test_read_events_range_and_garbage(isolated_proc_events):
    isolated_proc_events.mkdir(parents=True)
    (isolated_proc_events / "proc-events-2020-01.log").write_text(
        '{"ts":"2020-01-05T10:00:00+00:00","component":"pm","event":"start"}\nnot json\n[1]\n'
    )
    proc_events.record("pm", "exit")
    assert len(list(proc_events.read_events())) == 2
    since = datetime(2021, 1, 1, tzinfo=UTC)
    assert [e["event"] for e in proc_events.read_events(start=since)] == ["exit"]
    assert [e["event"] for e in proc_events.read_events(end=since)] == ["start"]


def test_recent_events_filters():
    proc_events.record("supervisor", "start", name="web")
    proc_events.record("supervisor", "service.stop", name="web", actor="api")
    proc_events.record("scheduler", "task.run_now", name="job", actor="cli")
    proc_events.record("pm", "exit", run_id="p1")
    assert [e["event"] for e in proc_events.recent_events(2)] == ["exit", "task.run_now"]
    assert [e["event"] for e in proc_events.recent_events(audit=True)] == ["task.run_now", "service.stop"]
    assert [e["event"] for e in proc_events.recent_events(audit=False)] == ["exit", "start"]
    assert [e["event"] for e in proc_events.recent_events(component="supervisor", event="service.")] == ["service.stop"]
    assert [e["event"] for e in proc_events.recent_events(name="web")] == ["service.stop", "start"]


def test_csv_export():
    proc_events.record("pm", "exit", run_id="p1", cmd=["echo", "a,b"], exit_code=0, state="completed", extra=1)
    text = "".join(proc_events.to_csv_rows(proc_events.read_events()))
    rows = list(csv.DictReader(io.StringIO(text)))
    assert list(rows[0]) == list(proc_events.CSV_COLUMNS)
    assert rows[0]["cmd"] == "echo a,b"
    assert rows[0]["exit_code"] == "0"
    assert json.loads(rows[0]["details"]) == {"extra": 1}


def test_prune(isolated_proc_events):
    isolated_proc_events.mkdir(parents=True)
    for month in ("2001-01", "2001-02"):
        (isolated_proc_events / f"proc-events-{month}.log").write_text("")
    proc_events.record("pm", "start")
    removed = proc_events.prune(keep_months=2)
    assert sorted(os.path.basename(p) for p in removed) == ["proc-events-2001-01.log", "proc-events-2001-02.log"]
    assert len(proc_events.log_files()) == 1
    assert proc_events.prune(keep_months=0) == []


# -- hooks --------------------------------------------------------------------


def test_pm_records_start_and_exit(tmp_path):
    async def main():
        pm = ProcessManager(str(tmp_path / "procs"))
        a = await pm.start(
            ["sh", "-c", "exit 3"], origin={"component": "scheduler", "name": "job", "trigger": "manual"}
        )
        b = await pm.start("true")
        await pm.wait(a.pid)
        await pm.wait(b.pid)
        return a, b

    a, b = asyncio.run(main())
    start, exit_ = _events(run_id=a.pid)
    assert start["event"] == "start" and start["component"] == "scheduler" and start["name"] == "job"
    assert start["trigger"] == "manual" and start["system_pid"] == a.system_pid
    assert exit_["event"] == "exit" and exit_["state"] == "failed" and exit_["exit_code"] == 3
    assert exit_["duration_ms"] >= 0
    assert [e["component"] for e in _events(run_id=b.pid)] == ["pm", "pm"]


def test_pm_records_spawn_error(tmp_path):
    with pytest.raises(OSError):
        asyncio.run(ProcessManager(str(tmp_path / "procs")).start(["/nonexistent/binary"], pid="bad"))
    (event,) = _events(event="spawn_error")
    assert event["run_id"] == "bad" and "FileNotFoundError" in event["error"]


def test_scheduler_callable_run_events():
    def boom():
        raise ValueError("nope")

    asyncio.run(ScheduledTask(name="ok", interval="cron:* * * * *", run_fn=lambda: None).run(trigger="manual"))
    asyncio.run(ScheduledTask(name="bad", interval="cron:* * * * *", run_fn=boom).run())
    ok = _events(name="ok")
    assert [e["event"] for e in ok] == ["start", "exit"]
    assert ok[1]["state"] == "completed" and ok[1]["trigger"] == "manual"
    assert ok[0]["run_id"] == ok[1]["run_id"]
    bad_exit = _events(name="bad", event="exit")[0]
    assert bad_exit["state"] == "failed" and "ValueError: nope" in bad_exit["error"]


def test_scheduler_cmd_timeout(tmp_path):
    task = ScheduledTask(name="slow", interval="cron:* * * * *", cmd=["sleep", "5"], timeout=0.3)
    asyncio.run(task.run(ProcessManager(str(tmp_path / "procs"))))
    events = _events(name="slow")
    assert [e["event"] for e in events] == ["start", "timeout", "exit"] or [e["event"] for e in events] == [
        "start",
        "exit",
        "timeout",
    ]
    assert all(e["component"] == "scheduler" for e in events)
    assert _events(name="slow", event="exit")[0]["state"] == "killed"
    assert _events(name="slow", event="timeout")[0]["run_id"] == task.last_run_id


def test_supervisor_run_events(monkeypatch):
    monkeypatch.setattr(sup_mod, "BACKOFF_INITIAL", 0.05)

    async def main():
        sup = Supervisor()
        await sup.ensure("crash", ProcConfig(name="crash", cmd=["sh", "-c", "exit 2"]))
        await sup.ensure("long", ProcConfig(name="long", cmd=["sleep", "30"]))
        await asyncio.sleep(0.5)
        await sup.stop_process("long")
        await sup.stop()

    asyncio.run(main())
    crash = _events(name="crash")
    kinds = [e["event"] for e in crash]
    assert kinds[:3] == ["start", "exit", "restart_scheduled"]
    assert crash[0]["trigger"] == "start"
    assert _events(name="crash", event="start")[1]["trigger"] == "restart"
    assert crash[1]["state"] == "failed" and crash[1]["exit_code"] == 2
    long_exit = _events(name="long", event="exit")
    assert len(long_exit) == 1 and long_exit[0]["state"] == "killed"


def test_host_audit_events_carry_the_actor(tmp_path):
    services = tmp_path / "services.json"
    services.write_text(json.dumps({"services": [{"name": "svc", "cmd": ["sleep", "30"]}]}))

    async def main():
        host = ProcessHost(
            pm=ProcessManager(str(tmp_path / "procs")),
            scheduler=Scheduler(),
            supervisor=Supervisor(),
            services_config=str(services),
        )
        await host.start()
        try:
            await host.methods["supervisor.restart"]({"name": "svc", "actor": "api"})
            await host.methods["supervisor.stop"]({"name": "svc", "disable_restart": False, "actor": "cli"})
            await host.methods["supervisor.reload"]({})
            info = await host.methods["pm.start"]({"command": ["sleep", "30"], "actor": "agent"})
            await host.methods["pm.kill"]({"process_id": info["pid"], "actor": "api"})
        finally:
            await host.stop()
        return info

    info = asyncio.run(main())
    assert _events(event="service.restart")[0]["actor"] == "api"
    stop = _events(event="service.stop")[0]
    assert stop["actor"] == "cli" and stop["keep"] is True
    assert _events(event="config.reload")[0]["actor"] == "unknown"
    start = _events(run_id=info["pid"], event="start")[0]
    assert start["component"] == "pm" and start["actor"] == "agent" and start["trigger"] == "manual"
    assert _events(event="pm.kill")[0]["run_id"] == info["pid"]


# -- stats --------------------------------------------------------------------


def _write_log(log_dir, lines):
    log_dir.mkdir(parents=True, exist_ok=True)
    (log_dir / "proc-events-2026-01.log").write_text("".join(json.dumps(line) + "\n" for line in lines))


def test_proc_stats(isolated_proc_events):
    ts = "2026-01-10T12:00:00+00:00"
    local_day = datetime.fromisoformat(ts).astimezone().date()
    _write_log(
        isolated_proc_events,
        [
            {"ts": ts, "component": "scheduler", "event": "start", "name": "job"},
            {
                "ts": ts,
                "component": "scheduler",
                "event": "exit",
                "name": "job",
                "state": "completed",
                "duration_ms": 100,
            },
            {"ts": ts, "component": "scheduler", "event": "exit", "name": "job", "state": "failed", "duration_ms": 300},
            {"ts": ts, "component": "scheduler", "event": "timeout", "name": "job"},
            {"ts": ts, "component": "supervisor", "event": "restart_scheduled", "name": "web"},
            {"ts": ts, "component": "supervisor", "event": "service.stop", "name": "web"},
            {"ts": ts, "component": "pm", "event": "exit", "state": "killed"},
        ],
    )
    stats = proc_stats.proc_stats(local_day - timedelta(days=1), local_day)
    t = stats["totals"]
    assert (t["runs"], t["completed"], t["failed"], t["killed"]) == (3, 1, 1, 1)
    assert (t["timeouts"], t["restarts"], t["actions"]) == (1, 1, 1)
    assert t["avg_duration_ms"] == 200
    assert len(stats["daily"]) == 2 and stats["daily"][1]["runs"] == 3
    assert sum(stats["hourly"]) == 1
    assert [r["key"] for r in stats["by_component"]] == ["scheduler", "pm", "supervisor"]
    job = next(r for r in stats["by_name"] if r["key"] == "scheduler:job")
    assert (job["component"], job["name"], job["runs"]) == ("scheduler", "job", 2)
    assert any(r["name"] == proc_stats.ADHOC_NAME for r in stats["by_name"])
    with pytest.raises(ValueError):
        proc_stats.proc_stats(date(2026, 2, 1), date(2026, 1, 1))


def test_stats_routes(isolated_proc_events):
    proc_events.record("pm", "start", run_id="p1", cmd=["echo", "hi"])
    proc_events.record("pm", "exit", run_id="p1", state="completed", exit_code=0, duration_ms=5)
    proc_events.record("supervisor", "service.stop", name="web", actor="api")
    api = TestClient(app)

    stats = api.get("/api/v1/stats/processes?days=7").json()
    assert stats["totals"]["runs"] == 1 and stats["totals"]["actions"] == 1
    assert len(stats["daily"]) == 7

    events = api.get("/api/v1/stats/processes/events?audit=true").json()["events"]
    assert [e["event"] for e in events] == ["service.stop"]

    res = api.get("/api/v1/stats/processes/events.csv?days=1")
    assert res.headers["content-type"].startswith("text/csv")
    assert "attachment" in res.headers["content-disposition"]
    rows = list(csv.DictReader(io.StringIO(res.text)))
    assert [r["event"] for r in rows] == ["start", "exit", "service.stop"]

    assert api.get("/api/v1/stats/processes?start=2026-02-01&end=2026-01-01").status_code == 400
