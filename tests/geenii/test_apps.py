import asyncio
import json
import os
import shutil
import tempfile
import threading
import time

import pytest
from click.testing import CliRunner

from geenii.apps import AppRegistry, AppType, GeeAppManifest, infer_manifest, write_manifest
from geenii.cli import apps_cli
from geenii.daemon.client import DaemonClient
from geenii.daemon.host import ProcessHost
from geenii.daemon.server import DaemonServer
from geenii.pm.process_manager import ProcessManager
from geenii.scheduler import Scheduler
from geenii.supervisor import Supervisor

PY_APP = 'import os, time\nprint("listening on", os.environ["PORT"], flush=True)\ntime.sleep(30)\n'


@pytest.fixture
def short_dir():
    # Unix socket paths are limited to ~104 bytes on macOS; pytest's tmp_path is often longer
    d = tempfile.mkdtemp(prefix="ga", dir="/tmp" if os.path.isdir("/tmp") else None)
    yield d
    shutil.rmtree(d, ignore_errors=True)


def _wait_until(predicate, timeout: float = 5.0, interval: float = 0.05):
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(interval)
    raise AssertionError("condition not met in time")


class RunningDaemon:
    """Runs a DaemonServer on its own event loop thread."""

    def __init__(self, server: DaemonServer):
        self.server = server
        self.loop = asyncio.new_event_loop()
        self.error: BaseException | None = None
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.server.start())
            self.loop.run_until_complete(self.server._stop_event.wait())
            self.loop.run_until_complete(self.server.stop())
        except BaseException as exc:
            self.error = exc

    def __enter__(self):
        self._thread.start()
        client = DaemonClient(self.server.socket_path)
        _wait_until(lambda: client.is_available() or self.error)
        if self.error:
            raise self.error
        return client

    def __exit__(self, *exc):
        if self._thread.is_alive():
            self.loop.call_soon_threadsafe(self.server.request_shutdown)
            self._thread.join(15)


def _make_app(apps_dir: str, name: str, files: dict[str, str]) -> str:
    app_dir = os.path.join(apps_dir, name)
    os.makedirs(app_dir)
    for fname, content in files.items():
        with open(os.path.join(app_dir, fname), "w") as f:
            f.write(content)
    return app_dir


def _make_host(short_dir, apps_dirs) -> ProcessHost:
    return ProcessHost(
        pm=ProcessManager(os.path.join(short_dir, "procs")),
        scheduler=Scheduler(),
        supervisor=Supervisor(),
        apps=AppRegistry(apps_dirs),
    )


def test_infer_python_app(tmp_path):
    (tmp_path / "app.py").write_text("")
    manifest = infer_manifest(str(tmp_path), "x")
    assert manifest.type == AppType.PYTHON and manifest.main == "app.py"


def test_service_config_has_only_app_env(tmp_path):
    app_dir = _make_app(str(tmp_path), "web", {"index.html": ""})
    write_manifest(app_dir, GeeAppManifest(name="web", env={"A": "1"}))
    registry = AppRegistry([str(tmp_path)])
    registry.reload()
    config = registry.require("web").to_service_config(port=9200)
    assert config.name == "app-web"
    assert config.cmd == ["python3", "-m", "http.server", "9200"]
    assert config.env == {"A": "1", "PORT": "9200"}
    assert config.cwd == app_dir
    proc = config.to_proc_config()
    assert proc.cmd == config.cmd and proc.env == config.env


def test_reload_keeps_assigned_ports_and_reports_changes(tmp_path):
    _make_app(str(tmp_path), "one", {"index.html": ""})
    registry = AppRegistry([str(tmp_path)])
    assert registry.reload() == {"added": ["one"], "removed": []}
    port = registry.assign_port("one")
    assert 42000 <= port <= 44000

    _make_app(str(tmp_path), "two", {"index.html": ""})
    assert registry.reload() == {"added": ["two"], "removed": []}
    assert registry.require("one").port == port
    # Allocated ports don't collide with other apps' ports
    assert registry.assign_port("two") != port


def test_invalid_manifest_is_skipped(tmp_path):
    app_dir = _make_app(str(tmp_path), "bad", {})
    with open(os.path.join(app_dir, "manifest.json"), "w") as f:
        f.write("{not json")
    registry = AppRegistry([str(tmp_path)])
    registry.reload()
    assert registry.names() == []


def test_apps_run_as_supervisor_services(short_dir):
    user_apps = os.path.join(short_dir, "user-apps")
    project_apps = os.path.join(short_dir, "project-apps")
    _make_app(user_apps, "pyapp", {"main.py": PY_APP})
    _make_app(project_apps, "projapp", {"main.py": PY_APP})
    socket_path = os.path.join(short_dir, "d.sock")

    with RunningDaemon(DaemonServer(_make_host(short_dir, [user_apps]), socket_path)) as client:
        assert [a["name"] for a in client.call("apps.list")] == ["pyapp"]
        # Clients bring their own app directories
        assert [a["name"] for a in client.call("apps.list", {"dirs": [project_apps]})] == ["projapp", "pyapp"]
        assert client.info()["apps"]["dirs"] == [user_apps, project_apps]

        info = client.call("apps.start", {"name": "pyapp", "port": 9555})
        assert info["service"] == "app-pyapp" and info["port"] == 9555
        _wait_until(lambda: client.call("apps.info", {"name": "pyapp"})["status"] == "running")
        assert "app-pyapp" in client.call("supervisor.status")["running"]
        _wait_until(lambda: "[stdout] listening on 9555" in client.call("apps.logs", {"name": "pyapp"}))

        with pytest.raises(RuntimeError, match="already started"):
            client.call("apps.start", {"name": "pyapp"})

        first = client.call("apps.info", {"name": "pyapp"})["pid"]
        client.call("apps.restart", {"name": "pyapp"})
        _wait_until(lambda: client.call("apps.info", {"name": "pyapp"})["pid"] not in (None, first))
        # The port sticks across restarts
        assert client.call("apps.info", {"name": "pyapp"})["port"] == 9555

        info = client.call("apps.stop", {"name": "pyapp"})
        assert info["status"] == "stopped"
        assert "app-pyapp" not in client.call("supervisor.status")["desired"]
        with pytest.raises(RuntimeError, match="not running"):
            client.call("apps.stop", {"name": "pyapp"})
        with pytest.raises(RuntimeError, match="not found"):
            client.call("apps.start", {"name": "missing"})
        with pytest.raises(RuntimeError, match="absolute"):
            client.call("apps.list", {"dirs": ["relative/dir"]})

        _make_app(user_apps, "later", {"index.html": ""})
        result = client.call("apps.reload")
        assert result["added"] == ["later"] and result["removed"] == []


def test_apps_cli(short_dir, monkeypatch):
    apps_dir = os.path.join(short_dir, "apps")
    _make_app(apps_dir, "pyapp", {"main.py": PY_APP})
    socket_path = os.path.join(short_dir, "d.sock")
    # Keep the real ~/.geenii/apps and project apps out of the test
    monkeypatch.setattr(apps_cli, "apps_dirs", lambda: [apps_dir])

    def cli(*args):
        result = CliRunner().invoke(apps_cli.apps, list(args), env={"COLUMNS": "250", "GEENII_SOCKET": socket_path})
        return result.exit_code, result.output

    code, out = cli("list")
    assert code == 1 and "not running" in out

    with RunningDaemon(DaemonServer(_make_host(short_dir, []), socket_path)) as client:
        code, out = cli("list", "--json")
        assert code == 0 and [a["name"] for a in json.loads(out)] == ["pyapp"]

        code, out = cli("start", "pyapp", "--port", "9556")
        assert code == 0 and "Started 'pyapp'" in out and "9556" in out
        _wait_until(lambda: "running" in cli("list")[1])
        _wait_until(lambda: "listening on 9556" in cli("logs", "pyapp")[1])

        code, out = cli("start", "pyapp")
        assert code == 1 and "already started" in out

        code, out = cli("stop", "pyapp")
        assert code == 0 and "Stopped 'pyapp'" in out
        assert client.call("apps.info", {"name": "pyapp"})["status"] == "stopped"

        # init writes the manifest and the running daemon picks it up
        _make_app(apps_dir, "site", {"index.html": ""})
        code, out = cli("init", "site", "--title", "My Site")
        assert code == 0 and os.path.isfile(os.path.join(apps_dir, "site", "manifest.json"))
        assert client.call("apps.info", {"name": "site"})["title"] == "My Site"


@pytest.fixture
def api():
    """Factory for a TestClient whose apps routes use the given daemon socket and app directories."""
    from fastapi.testclient import TestClient

    from geenii.server import apps_routes, daemon_helper
    from geenii.server.server import app

    def _api(socket_path, dirs):
        app.dependency_overrides[daemon_helper.dep_daemon_client] = lambda: DaemonClient(socket_path, actor="api")
        app.dependency_overrides[apps_routes.dep_apps_dirs] = lambda: dirs
        return TestClient(app)

    yield _api
    app.dependency_overrides.clear()


def test_apps_routes_without_daemon(short_dir, api):
    apps_dir = os.path.join(short_dir, "apps")
    _make_app(apps_dir, "site", {"index.html": ""})
    http = api(os.path.join(short_dir, "d.sock"), [apps_dir])

    body = http.get("/api/v1/apps/").json()
    assert body["daemon"] == {"running": False}
    assert [(a["name"], a["type"], a["status"]) for a in body["apps"]] == [("site", "statichtml", None)]
    assert http.get("/api/v1/apps/site").json()["service"] == "app-site"
    assert http.get("/api/v1/apps/missing").status_code == 404

    resp = http.post("/api/v1/apps/site/start")
    assert resp.status_code == 409 and "not running" in resp.json()["detail"]


def test_apps_routes_with_daemon(short_dir, api):
    apps_dir = os.path.join(short_dir, "apps")
    _make_app(apps_dir, "pyapp", {"main.py": PY_APP})
    socket_path = os.path.join(short_dir, "d.sock")
    http = api(socket_path, [apps_dir])

    with RunningDaemon(DaemonServer(_make_host(short_dir, []), socket_path)):
        body = http.get("/api/v1/apps/").json()
        assert body["daemon"] == {"running": True}
        assert [(a["name"], a["status"]) for a in body["apps"]] == [("pyapp", "stopped")]

        resp = http.post("/api/v1/apps/pyapp/start", json={"port": 9557})
        assert resp.status_code == 200 and resp.json()["port"] == 9557
        _wait_until(lambda: http.get("/api/v1/apps/pyapp").json()["status"] == "running")
        _wait_until(
            lambda: (
                "[stdout] listening on 9557" in http.get("/api/v1/apps/pyapp/logs", params={"tail": 10}).json()["lines"]
            )
        )

        resp = http.post("/api/v1/apps/pyapp/start")
        assert resp.status_code == 409 and "already started" in resp.json()["detail"]
        assert http.post("/api/v1/apps/pyapp/start", json={"port": 0}).status_code == 422

        first = http.get("/api/v1/apps/pyapp").json()["pid"]
        assert http.post("/api/v1/apps/pyapp/restart").status_code == 200
        _wait_until(lambda: http.get("/api/v1/apps/pyapp").json()["pid"] not in (None, first))

        resp = http.post("/api/v1/apps/pyapp/stop")
        assert resp.status_code == 200 and resp.json()["status"] == "stopped"
        assert http.post("/api/v1/apps/pyapp/stop").status_code == 409
        assert http.post("/api/v1/apps/missing/start").status_code == 404

        _make_app(apps_dir, "later", {"index.html": ""})
        resp = http.post("/api/v1/apps/reload")
        assert resp.status_code == 200 and resp.json()["added"] == ["later"]
