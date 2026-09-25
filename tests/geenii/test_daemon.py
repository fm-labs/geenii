import asyncio
import os
import shutil
import tempfile
import threading
import time

import pytest

from geenii.daemon.client import DaemonClient
from geenii.daemon.host import ProcessHost
from geenii.daemon.server import DaemonAlreadyRunning, DaemonServer
from geenii.pm.process_manager import ProcessManager
from geenii.pm.process_manager_client import ProcessManagerClient
from geenii.scheduler import ScheduledTask, Scheduler
from geenii.supervisor import Supervisor


@pytest.fixture
def short_dir():
    # Unix socket paths are limited to ~104 bytes on macOS; pytest's tmp_path is often longer
    d = tempfile.mkdtemp(prefix="gd", dir="/tmp" if os.path.isdir("/tmp") else None)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def _wait_until(predicate, timeout: float = 5.0, interval: float = 0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(interval)
    raise AssertionError("condition not met in time")


class RunningDaemon:
    """Runs a DaemonServer.serve_forever() on its own event loop thread."""

    def __init__(self, server: DaemonServer):
        self.server = server
        self.loop = asyncio.new_event_loop()
        self.error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        asyncio.set_event_loop(self.loop)
        try:
            # serve_forever() installs signal handlers, which only work in the main thread
            self.loop.run_until_complete(self.server.start())
            self.loop.run_until_complete(self.server._stop_event.wait())
            self.loop.run_until_complete(self.server.stop())
        except BaseException as exc:  # surfaced to the test
            self.error = exc

    def __enter__(self):
        self._thread.start()
        client = DaemonClient(self.server.socket_path)
        _wait_until(lambda: client.is_available() or self.error)
        if self.error:
            raise self.error
        return client

    def stop(self):
        self.loop.call_soon_threadsafe(self.server.request_shutdown)
        self._thread.join(15)

    def __exit__(self, *exc):
        if self._thread.is_alive():
            self.stop()


def _make_host(short_dir, scheduler=None) -> ProcessHost:
    return ProcessHost(
        pm=ProcessManager(os.path.join(short_dir, "procs")),
        scheduler=scheduler or Scheduler(),
        supervisor=Supervisor(),
    )


def test_one_socket_serves_all_three_components(short_dir):
    scheduler = Scheduler()
    marker = os.path.join(short_dir, "ran")
    asyncio.run(scheduler.add_task(ScheduledTask(
        name="touch", interval="cron:0 0 1 1 *", cmd=["touch", marker])))
    server = DaemonServer(_make_host(short_dir, scheduler), os.path.join(short_dir, "d.sock"))

    with RunningDaemon(server) as client:
        info = client.info()
        assert info["pid"] == os.getpid()
        assert info["scheduler"] == {"status": "running", "config": None, "tasks": 1, "running_tasks": 0}

        # Process manager, prefixed and via the legacy unprefixed alias
        pm = ProcessManagerClient(client.socket_path)
        a = pm.start(["echo", "prefixed"])
        b = client.call("start", {"command": "echo legacy"})
        _wait_until(lambda: pm.status(a["pid"])["state"] == "completed"
                    and pm.status(b["pid"])["state"] == "completed")
        assert pm.output(a["pid"]) == "prefixed\n"
        assert client.call("output", {"process_id": b["pid"]}) == "legacy\n"

        # Scheduler: live status and a manual run
        status = client.call("scheduler.status")
        assert [t["name"] for t in status["tasks"]] == ["touch"]
        assert client.call("scheduler.run", {"name": "touch"}) == "started"
        _wait_until(lambda: os.path.exists(marker))
        with pytest.raises(RuntimeError, match="KeyError"):
            client.call("scheduler.run", {"name": "missing"})

        # Supervisor: ensure, logs, restart, stop
        assert client.call("supervisor.ensure", {
            "name": "ticker", "cmd": ["sh", "-c", "echo tick; sleep 30"]}) == "ok"
        _wait_until(lambda: "ticker" in client.call("supervisor.status")["running"])
        first_pid = client.call("supervisor.status")["running"]["ticker"]["pid"]
        _wait_until(lambda: "[stdout] tick" in client.call("supervisor.logs", {"name": "ticker"}))
        client.call("supervisor.restart", {"name": "ticker"})
        _wait_until(lambda: client.call("supervisor.status")["running"].get("ticker", {}).get("pid")
                    not in (None, first_pid))
        client.call("supervisor.stop", {"name": "ticker"})
        assert client.call("supervisor.status")["desired"] == {}
        assert not _pid_alive(first_pid)

        with pytest.raises(RuntimeError, match="Unknown method"):
            client.call("nope.nothing")
        with pytest.raises(RuntimeError, match="non-empty list"):
            client.call("supervisor.ensure", {"name": "bad", "cmd": "not a list"})


def test_shutdown_stops_every_component_and_removes_the_socket(short_dir):
    server = DaemonServer(_make_host(short_dir), os.path.join(short_dir, "d.sock"))
    daemon = RunningDaemon(server)

    with daemon as client:
        pm_proc = ProcessManagerClient(client.socket_path).start(["sleep", "30"])
        client.call("supervisor.ensure", {"name": "svc", "cmd": ["sleep", "30"]})
        sup_pid = _wait_until(lambda: client.call("supervisor.status")["running"].get("svc", {}).get("pid"))

        assert client.shutdown() == "shutting down"
        daemon._thread.join(15)

    assert daemon.error is None
    assert not os.path.exists(server.socket_path)
    assert not _pid_alive(pm_proc["system_pid"])
    assert not _pid_alive(sup_pid)
    assert server.host.scheduler.status["status"] == "stopped"


def test_second_daemon_on_the_same_socket_is_refused(short_dir):
    socket_path = os.path.join(short_dir, "d.sock")
    first = DaemonServer(_make_host(short_dir), socket_path)

    with RunningDaemon(first) as client:
        second = DaemonServer(_make_host(os.path.join(short_dir, "b")), socket_path)
        with pytest.raises(DaemonAlreadyRunning):
            asyncio.run(second.start())
        # The first daemon is unaffected
        assert client.call("ping") == "pong"


def test_stale_socket_file_is_replaced(short_dir):
    socket_path = os.path.join(short_dir, "d.sock")
    with open(socket_path, "w"):
        pass  # leftover file, nothing listening

    with RunningDaemon(DaemonServer(_make_host(short_dir), socket_path)) as client:
        assert client.call("ping") == "pong"


# -- CLI commands backed by the daemon -----------------------------------------

import json  # noqa: E402

from click.testing import CliRunner  # noqa: E402

from geenii.cli.scheduler_cli import scheduler as scheduler_cli  # noqa: E402
from geenii.cli.supervisor_cli import supervisor as supervisor_cli  # noqa: E402
from geenii.daemon.server import build_host  # noqa: E402


@pytest.fixture
def cli(monkeypatch):
    def invoke(group, args, socket_path):
        monkeypatch.setenv("GEENII_SOCKET", socket_path)
        result = CliRunner().invoke(group, args, env={"COLUMNS": "250", "GEENII_SOCKET": socket_path})
        return result.exit_code, result.output
    return invoke


def _write_config(path, tasks):
    with open(path, "w") as f:
        json.dump({"tasks": tasks}, f)


def test_scheduler_cli_uses_the_live_daemon(short_dir, cli):
    config = os.path.join(short_dir, "scheduler.json")
    marker = os.path.join(short_dir, "ran")
    _write_config(config, [{"name": "touch", "interval": "cron:0 0 1 1 *", "cmd": ["touch", marker]}])
    host = build_host(config)
    host.pm = ProcessManager(os.path.join(short_dir, "procs"))
    socket_path = os.path.join(short_dir, "d.sock")

    with RunningDaemon(DaemonServer(host, socket_path)):
        code, out = cli(scheduler_cli, ["status", "-c", config], socket_path)
        assert code == 0 and "— live" in out and "touch" in out and "idle" in out

        # run: starts in the daemon and returns immediately
        code, out = cli(scheduler_cli, ["run", "touch", "-c", config], socket_path)
        assert code == 0 and "in the running daemon" in out
        _wait_until(lambda: os.path.exists(marker))

        # add/remove edit the file and reload the daemon
        code, out = cli(scheduler_cli, ["add", "extra", "true", "-i", "cron:0 0 1 1 *", "--config", config],
                        socket_path)
        assert code == 0 and "Reloaded the running daemon (added: extra)" in out
        assert [t.name for t in host.scheduler.tasks] == ["touch", "extra"]
        code, out = cli(scheduler_cli, ["remove", "touch", "--config", config], socket_path)
        assert code == 0 and "removed: touch" in out
        assert [t.name for t in host.scheduler.tasks] == ["extra"]

        # a hand-edited file needs an explicit reload
        _write_config(config, [{"name": "manual", "interval": "cron:0 0 1 1 *", "cmd": ["true"]}])
        code, out = cli(scheduler_cli, ["reload", "-c", config], socket_path)
        assert code == 0 and "added: manual" in out and "removed: extra" in out

        # another config file: not the daemon's, so commands work offline on the file
        other = os.path.join(short_dir, "other.json")
        other_marker = os.path.join(short_dir, "other-ran")
        _write_config(other, [{"name": "o", "interval": "cron:0 0 1 1 *", "cmd": ["touch", other_marker]}])
        code, out = cli(scheduler_cli, ["status", "-c", other], socket_path)
        assert code == 0 and "different config" in out and "— live" not in out
        code, out = cli(scheduler_cli, ["run", "o", "-c", other], socket_path)
        assert code == 0 and "Running locally" in out and os.path.exists(other_marker)
        code, out = cli(scheduler_cli, ["reload", "-c", other], socket_path)
        assert code == 1 and "different config" in out


def test_scheduler_cli_without_daemon_reads_the_file(short_dir, cli):
    config = os.path.join(short_dir, "scheduler.json")
    _write_config(config, [{"name": "t", "interval": "cron:0 0 1 1 *", "cmd": ["true"]}])
    socket_path = os.path.join(short_dir, "none.sock")

    code, out = cli(scheduler_cli, ["status", "-c", config], socket_path)
    assert code == 0 and "not running" in out and "t" in out
    code, out = cli(scheduler_cli, ["add", "u", "true", "-i", "cron:0 0 1 1 *", "--config", config], socket_path)
    assert code == 0 and "Reloaded" not in out


def test_supervisor_cli(short_dir, cli):
    socket_path = os.path.join(short_dir, "d.sock")

    code, out = cli(supervisor_cli, ["status"], socket_path)
    assert code == 1 and "not running" in out

    with RunningDaemon(DaemonServer(_make_host(short_dir), socket_path)) as client:
        code, out = cli(supervisor_cli, ["start", "tick", "-e", "WORD=tock", "--",
                                         "sh", "-c", "echo $WORD; sleep 30"], socket_path)
        assert code == 0 and "Supervising 'tick'" in out
        _wait_until(lambda: "tick" in client.call("supervisor.status")["running"])

        code, out = cli(supervisor_cli, ["status"], socket_path)
        assert code == 0 and "tick" in out and "running" in out

        _wait_until(lambda: "[stdout] tock" in cli(supervisor_cli, ["logs", "tick"], socket_path)[1])

        first = client.call("supervisor.status")["running"]["tick"]["pid"]
        code, _ = cli(supervisor_cli, ["restart", "tick"], socket_path)
        assert code == 0
        _wait_until(lambda: client.call("supervisor.status")["running"].get("tick", {}).get("pid")
                    not in (None, first))

        code, _ = cli(supervisor_cli, ["stop", "tick", "--keep"], socket_path)
        assert code == 0
        code, out = cli(supervisor_cli, ["status", "--json"], socket_path)
        st = json.loads(out)
        assert "tick" in st["desired"] and "tick" not in st["running"]

        code, _ = cli(supervisor_cli, ["stop", "tick"], socket_path)
        assert code == 0 and client.call("supervisor.status")["desired"] == {}

        code, out = cli(supervisor_cli, ["restart", "missing"], socket_path)
        assert code == 1 and "KeyError" in out


def test_scheduled_runs_are_process_manager_processes(short_dir, cli):
    from geenii.cli.pm_cli import pm as pm_cli

    scheduler = Scheduler()
    asyncio.run(scheduler.add_task(ScheduledTask(
        name="report", interval="cron:0 0 1 1 *", cmd=["sh", "-c", "echo report done; exit 3"])))
    socket_path = os.path.join(short_dir, "d.sock")

    with RunningDaemon(DaemonServer(_make_host(short_dir, scheduler), socket_path)) as client:
        client.call("scheduler.run", {"name": "report"})
        run_id = _wait_until(lambda: client.call("scheduler.status")["tasks"][0]["last_run_id"])

        pm = ProcessManagerClient(socket_path)
        final = pm.wait(run_id, timeout=5)
        assert (final["state"], final["exit_code"]) == ("failed", 3)
        assert pm.output(run_id) == "report done\n"
        assert run_id in {p["pid"] for p in pm.list(include_finished=True)}

        # `geenii pm wait` exits with the process's exit code
        code, out = cli(pm_cli, ["wait", run_id], socket_path)
        assert code == 3 and '"exit_code": 3' in out
        with pytest.raises(RuntimeError, match="TimeoutError"):
            long = pm.start(["sleep", "30"])
            pm.wait(long["pid"], timeout=0.2)


# -- services config file --------------------------------------------------------

def _services(path, services):
    with open(path, "w") as f:
        json.dump({"services": services}, f)


def test_daemon_starts_and_reloads_configured_services(short_dir, cli):
    services_path = os.path.join(short_dir, "services.json")
    _services(services_path, [
        {"name": "web", "cmd": ["sh", "-c", "echo up; sleep 30"]},
        {"name": "off", "cmd": ["true"], "enabled": False},
    ])
    host = build_host(None, services_path)
    host.pm = ProcessManager(os.path.join(short_dir, "procs"))
    socket_path = os.path.join(short_dir, "d.sock")

    with RunningDaemon(DaemonServer(host, socket_path)) as client:
        assert client.info()["supervisor"]["config"] == os.path.abspath(services_path)
        _wait_until(lambda: "web" in client.call("supervisor.status")["running"])
        assert set(client.call("supervisor.status")["desired"]) == {"web"}

        # CLI add/remove edit the file and reload the daemon
        code, out = cli(supervisor_cli, ["add", "worker", "-e", "X=1", "-c", services_path,
                                         "--", "sleep", "30"], socket_path)
        assert code == 0 and "Reloaded the running daemon (started: worker)" in out
        _wait_until(lambda: "worker" in client.call("supervisor.status")["running"])
        code, out = cli(supervisor_cli, ["add", "worker", "-c", services_path, "--", "true"], socket_path)
        assert code == 1 and "already exists" in out

        code, out = cli(supervisor_cli, ["list", "-c", services_path], socket_path)
        assert "web" in out and "worker" in out and "(disabled)" in out

        code, out = cli(supervisor_cli, ["status"], socket_path)
        assert code == 0 and "file" in out

        code, out = cli(supervisor_cli, ["remove", "web", "-c", services_path], socket_path)
        assert code == 0 and "stopped: web" in out
        assert set(client.call("supervisor.status")["desired"]) == {"worker"}

        # hand edit + reload: a changed service restarts
        _services(services_path, [{"name": "worker", "cmd": ["sleep", "31"]}])
        code, out = cli(supervisor_cli, ["reload", "-c", services_path], socket_path)
        assert code == 0 and "restarted: worker" in out

        # a different file isn't the daemon's: no reload
        other = os.path.join(short_dir, "other.json")
        code, out = cli(supervisor_cli, ["add", "x", "-c", other, "--", "true"], socket_path)
        assert code == 0 and "Reloaded" not in out
        code, out = cli(supervisor_cli, ["reload", "-c", other], socket_path)
        assert code == 1 and "different config" in out


def test_broken_services_file_does_not_stop_the_daemon(short_dir):
    services_path = os.path.join(short_dir, "services.json")
    with open(services_path, "w") as f:
        f.write("{not json")
    host = build_host(None, services_path)
    host.pm = ProcessManager(os.path.join(short_dir, "procs"))

    with RunningDaemon(DaemonServer(host, os.path.join(short_dir, "d.sock"))) as client:
        assert client.call("ping") == "pong"
        with pytest.raises(RuntimeError, match="JSONDecodeError"):
            client.call("supervisor.reload")
