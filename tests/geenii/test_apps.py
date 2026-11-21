import asyncio
import json
import os
import shutil
import tempfile
import threading
import time

import pydantic
import pytest
from click.testing import CliRunner

from geenii import config
from geenii.apps import (
    PYTHON_LAUNCH_SCRIPTS,
    AppRegistry,
    AppType,
    GeeAppManifest,
    app_venv_dir,
    infer_manifest,
    save_app_settings,
    write_manifest,
)
from geenii.cli import apps_cli
from geenii.daemon.client import DaemonClient
from geenii.daemon.host import ProcessHost
from geenii.daemon.server import DaemonServer
from geenii.pm.process_manager import ProcessManager
from geenii.scheduler import Scheduler
from geenii.supervisor import Supervisor

PY_APP = 'import os, time\nprint("listening on", os.environ["PORT"], flush=True)\ntime.sleep(30)\n'


@pytest.fixture(autouse=True)
def user_home(tmp_path, monkeypatch):
    """Keep the user settings (app settings) out of the real ~/.geenii. Returns the settings file path."""
    # a dot dir: tests that scan tmp_path for apps skip it
    monkeypatch.setattr(config, "GEENII_USER_HOME", str(tmp_path / ".home"))
    # ...and the managed venvs of python apps out of the real cache dir
    monkeypatch.setattr(config, "GEENII_CACHE_DIR", str(tmp_path / ".cache"))
    return config.user_settings_path()


def _read_settings(path):
    with open(path) as f:
        return json.load(f)


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


def _make_app(apps_dir: str, name: str, files: dict[str, str], enabled: bool = True) -> str:
    """An app directory with FILES; enabled in the user settings unless ENABLED is false (apps are disabled by default)"""
    app_dir = os.path.join(apps_dir, name)
    os.makedirs(app_dir)
    for fname, content in files.items():
        with open(os.path.join(app_dir, fname), "w") as f:
            f.write(content)
    if enabled:
        save_app_settings(app_dir, enabled=True)
    return app_dir


def _make_host(short_dir, apps_dirs) -> ProcessHost:
    return ProcessHost(
        pm=ProcessManager(os.path.join(short_dir, "procs")),
        scheduler=Scheduler(),
        supervisor=Supervisor(),
        apps=AppRegistry(apps_dirs),
    )


def test_inferred_manifest_title(tmp_path):
    app_dir = _make_app(str(tmp_path), "my-cool_app", {"index.html": ""})
    assert infer_manifest(app_dir, "my-cool_app").title == "My Cool App"


def test_infer_python_app(tmp_path):
    (tmp_path / "app.py").write_text("")
    manifest = infer_manifest(str(tmp_path), "x")
    assert manifest.type == AppType.PYTHON and manifest.main == "app.py"


def _python_service(tmp_path, files, **manifest):
    app_dir = _make_app(str(tmp_path), "py", files)
    write_manifest(app_dir, GeeAppManifest(name="py", title="Py", type="python", **manifest))
    registry = AppRegistry([str(tmp_path)])
    registry.reload()
    return app_dir, registry.require("py").to_service_config(port=9300)


@pytest.mark.parametrize(
    "files, kind",
    [
        ({"main.py": "", "pyproject.toml": "", "uv.lock": "", "requirements.txt": ""}, "uv.lock"),
        ({"main.py": "", "pyproject.toml": "", "requirements.txt": ""}, "pyproject.toml"),
        ({"main.py": "", "requirements.txt": ""}, "requirements.txt"),
        ({"main.py": "# /// script\n# dependencies = []\n# ///\n"}, "script"),
        ({"main.py": ""}, "plain"),
    ],
)
def test_python_app_runs_in_a_managed_venv(tmp_path, files, kind):
    app_dir, conf = _python_service(tmp_path, files, python="3.12")
    venv = app_venv_dir(app_dir, "py", "3.12")
    assert venv.startswith(os.path.join(config.GEENII_CACHE_DIR, "app-venvs", "py-"))
    assert conf.cmd == ["sh", "-c", PYTHON_LAUNCH_SCRIPTS[kind], "sh", venv, "3.12", os.path.realpath(app_dir), "main.py"]
    assert conf.env["PYTHONPATH"] == "" and conf.env["PYTHONUNBUFFERED"] == "1"
    if kind == "script":
        assert conf.env["VIRTUAL_ENV"] == ""
    else:
        assert conf.env["VIRTUAL_ENV"] == venv
        assert conf.env["PATH"].split(os.pathsep)[0] == os.path.join(venv, "bin")
    assert ("UV_PROJECT_ENVIRONMENT" in conf.env) == (kind == "uv.lock")


def test_python_app_venv_depends_on_dir_and_python(tmp_path):
    assert app_venv_dir(str(tmp_path / "a"), "x") != app_venv_dir(str(tmp_path / "b"), "x")
    assert app_venv_dir(str(tmp_path / "a"), "x") != app_venv_dir(str(tmp_path / "a"), "x", "3.12")


def test_python_app_with_own_venv_uses_it(tmp_path):
    app_dir = _make_app(str(tmp_path), "py", {"main.py": ""})
    python = os.path.join(app_dir, ".venv", "bin", "python")
    os.makedirs(os.path.dirname(python))
    with open(python, "w"):
        pass
    os.chmod(python, 0o755)
    write_manifest(app_dir, GeeAppManifest(name="py", title="Py", type="python"))
    registry = AppRegistry([str(tmp_path)])
    registry.reload()
    conf = registry.require("py").to_service_config()
    assert conf.cmd == [python, "main.py"]
    assert conf.env["VIRTUAL_ENV"] == os.path.join(app_dir, ".venv")


def test_python_app_without_uv_fails_clearly(tmp_path, monkeypatch):
    monkeypatch.setattr("geenii.apps.shutil.which", lambda _: None)
    with pytest.raises(FileNotFoundError, match="'uv' is needed"):
        _python_service(tmp_path, {"main.py": ""})


def test_service_config_has_only_app_env(tmp_path):
    app_dir = _make_app(str(tmp_path), "web", {"index.html": ""})
    write_manifest(app_dir, GeeAppManifest(name="web", title="Web", env={"A": "1"}))
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


def test_autostart_apps(short_dir):
    user_apps = os.path.join(short_dir, "user-apps")
    project_apps = os.path.join(short_dir, "project-apps")
    write_manifest(
        _make_app(user_apps, "auto", {"main.py": PY_APP}),
        GeeAppManifest(name="auto", title="Auto", type="python", autostart=True),
    )
    _make_app(user_apps, "manual", {"main.py": PY_APP})
    # A broken autostart app must not keep the others (or the daemon) from starting
    write_manifest(
        _make_app(user_apps, "broken", {}), GeeAppManifest(name="broken", title="Broken", type="binary", autostart=True)
    )
    write_manifest(
        _make_app(project_apps, "projauto", {"main.py": PY_APP}),
        GeeAppManifest(name="projauto", title="Projauto", type="python", autostart=True),
    )
    socket_path = os.path.join(short_dir, "d.sock")

    with RunningDaemon(DaemonServer(_make_host(short_dir, [user_apps]), socket_path)) as client:
        status = lambda name: client.call("apps.info", {"name": name})["status"]  # noqa: E731
        _wait_until(lambda: status("auto") == "running")
        assert client.call("apps.info", {"name": "auto"})["autostart"] is True
        assert status("manual") == "stopped"
        assert status("broken") == "stopped"

        # Apps in a newly added directory are autostarted when it is first scanned
        client.call("apps.list", {"dirs": [project_apps]})
        _wait_until(lambda: status("projauto") == "running")

        # A rescan doesn't restart an autostart app that was stopped on purpose
        client.call("apps.stop", {"name": "auto"})
        assert client.call("apps.reload")["autostarted"] == []
        assert status("auto") == "stopped"

        write_manifest(
            _make_app(user_apps, "later", {"main.py": PY_APP}),
            GeeAppManifest(name="later", title="Later", type="python", autostart=True),
        )
        assert client.call("apps.reload")["autostarted"] == ["later"]


def test_app_settings_are_saved_in_the_user_settings(tmp_path, user_home):
    app_dir = _make_app(str(tmp_path / "apps"), "web", {"index.html": ""}, enabled=False)
    os.makedirs(os.path.dirname(user_home))
    with open(user_home, "w") as f:
        json.dump({"theme": "dark", "apps": {"/other/app": {"enabled": False}}}, f)
    manifest_before = os.listdir(app_dir)

    # Apps are disabled until enabled in the settings
    registry = AppRegistry([str(tmp_path / "apps")])
    registry.reload()
    assert registry.require("web").enabled is False

    settings = save_app_settings(app_dir, autostart=True)
    assert settings.enabled is False and settings.autostart is True
    save_app_settings(app_dir, enabled=True)
    save_app_settings(app_dir, enabled=False)
    # Other settings stay; the app dir is untouched
    assert _read_settings(user_home) == {
        "theme": "dark",
        "apps": {"/other/app": {"enabled": False}, os.path.realpath(app_dir): {"autostart": True, "enabled": False}},
    }
    assert os.listdir(app_dir) == manifest_before

    registry = AppRegistry([str(tmp_path / "apps")])
    registry.reload()
    app = registry.require("web")
    assert (app.enabled, app.autostart) == (False, True)
    assert app.info()["enabled"] is False and app.info()["autostart"] is True


def test_settings_autostart_overrides_the_manifest(tmp_path):
    apps_dir = str(tmp_path / "apps")
    app_dir = _make_app(apps_dir, "web", {"index.html": ""})
    write_manifest(app_dir, GeeAppManifest(name="web", title="Web", autostart=True))
    registry = AppRegistry([apps_dir])
    registry.reload()
    assert registry.require("web").autostart is True
    save_app_settings(app_dir, autostart=False)
    registry.reload()
    assert registry.require("web").autostart is False


def test_malformed_settings_file_is_not_overwritten(tmp_path, user_home):
    app_dir = _make_app(str(tmp_path / "apps"), "web", {"index.html": ""}, enabled=False)
    os.makedirs(os.path.dirname(user_home))
    with open(user_home, "w") as f:
        f.write("{broken")
    with pytest.raises(ValueError):
        save_app_settings(app_dir, autostart=True)
    with open(user_home) as f:
        assert f.read() == "{broken"


def test_app_settings_routes(short_dir, api, user_home):
    apps_dir = os.path.join(short_dir, "apps")
    app_dir = _make_app(apps_dir, "pyapp", {"main.py": PY_APP})
    socket_path = os.path.join(short_dir, "d.sock")
    http = api(socket_path, [apps_dir])

    assert http.put("/api/v1/apps/pyapp/autostart", json={"autostart": True}).status_code == 409  # no daemon

    with RunningDaemon(DaemonServer(_make_host(short_dir, []), socket_path)) as client:
        resp = http.put("/api/v1/apps/pyapp/autostart", json={"autostart": True})
        assert resp.status_code == 200 and resp.json()["autostart"] is True
        # Setting the flag doesn't start the app, and doesn't write into the app dir
        assert resp.json()["status"] == "stopped"
        assert not os.path.exists(os.path.join(app_dir, "manifest.json"))
        assert _read_settings(user_home)["apps"] == {os.path.realpath(app_dir): {"enabled": True, "autostart": True}}
        # The registry re-reads the same value on rescans
        client.call("apps.reload")
        assert client.call("apps.info", {"name": "pyapp"})["autostart"] is True

        # Disabling a running app stops it, and a disabled app can't be started
        assert http.post("/api/v1/apps/pyapp/start").status_code == 200
        _wait_until(lambda: client.call("apps.info", {"name": "pyapp"})["status"] == "running")
        resp = http.put("/api/v1/apps/pyapp/enabled", json={"enabled": False})
        assert resp.status_code == 200 and resp.json()["enabled"] is False
        assert resp.json()["status"] == "stopped"
        assert "app-pyapp" not in client.call("supervisor.status")["desired"]
        resp = http.post("/api/v1/apps/pyapp/start")
        assert resp.status_code == 409 and "disabled" in resp.json()["detail"]
        assert http.post("/api/v1/apps/pyapp/restart").status_code == 409
        assert http.put("/api/v1/apps/pyapp/enabled", json={"enabled": True}).json()["enabled"] is True
        assert http.post("/api/v1/apps/pyapp/start").status_code == 200

        assert http.put("/api/v1/apps/pyapp/autostart", json={"autostart": "yes"}).status_code == 422
        assert http.put("/api/v1/apps/missing/enabled", json={"enabled": True}).status_code == 404


def test_autostart_skips_disabled_apps_and_uses_settings(short_dir):
    user_apps = os.path.join(short_dir, "user-apps")
    by_settings = _make_app(user_apps, "bysettings", {"main.py": PY_APP})
    # Never enabled: the manifest's autostart doesn't apply
    disabled = _make_app(user_apps, "disabled", {"main.py": PY_APP}, enabled=False)
    write_manifest(disabled, GeeAppManifest(name="disabled", title="Disabled", type="python", autostart=True))
    save_app_settings(by_settings, autostart=True)
    socket_path = os.path.join(short_dir, "d.sock")

    with RunningDaemon(DaemonServer(_make_host(short_dir, [user_apps]), socket_path)) as client:
        _wait_until(lambda: client.call("apps.info", {"name": "bysettings"})["status"] == "running")
        assert client.call("apps.info", {"name": "disabled"})["status"] == "stopped"


def test_apps_cli_settings(short_dir, monkeypatch, user_home):
    apps_dir = os.path.join(short_dir, "apps")
    app_dir = _make_app(apps_dir, "pyapp", {"main.py": PY_APP})
    socket_path = os.path.join(short_dir, "d.sock")
    monkeypatch.setattr(apps_cli, "apps_dirs", lambda: [apps_dir])

    def cli(*args):
        result = CliRunner().invoke(apps_cli.apps, list(args), env={"COLUMNS": "250", "GEENII_SOCKET": socket_path})
        return result.exit_code, result.output

    with RunningDaemon(DaemonServer(_make_host(short_dir, []), socket_path)):
        assert cli("autostart", "pyapp", "on")[0] == 0
        assert cli("disable", "pyapp")[0] == 0
        assert _read_settings(user_home)["apps"] == {os.path.realpath(app_dir): {"autostart": True, "enabled": False}}
        code, out = cli("start", "pyapp")
        assert code == 1 and "disabled" in out
        assert cli("enable", "pyapp")[0] == 0


def test_add_app_by_path(short_dir, api, user_home):
    apps_dir = os.path.join(short_dir, "apps")
    _make_app(apps_dir, "pyapp", {"main.py": PY_APP})
    elsewhere = os.path.join(short_dir, "elsewhere")
    ext_dir = _make_app(elsewhere, "ext-dir", {"main.py": PY_APP}, enabled=False)
    write_manifest(ext_dir, GeeAppManifest(name="ext", title="Ext", type="python"))
    no_manifest = _make_app(elsewhere, "plain", {"index.html": ""}, enabled=False)
    broken = _make_app(elsewhere, "broken", {"manifest.json": "{not json"}, enabled=False)
    clash = _make_app(elsewhere, "clash", {}, enabled=False)
    write_manifest(clash, GeeAppManifest(name="pyapp", title="Pyapp"))
    socket_path = os.path.join(short_dir, "d.sock")
    http = api(socket_path, [apps_dir])

    assert http.post("/api/v1/apps/add", json={"path": ext_dir}).status_code == 409  # no daemon

    with RunningDaemon(DaemonServer(_make_host(short_dir, []), socket_path)) as client:
        resp = http.post("/api/v1/apps/add", json={"path": ext_dir})
        assert resp.status_code == 200, resp.text
        info = resp.json()
        # Named after the manifest, added disabled
        assert (info["name"], info["enabled"], info["added"], info["status"]) == ("ext", False, True, "stopped")
        assert _read_settings(user_home)["apps"][os.path.realpath(ext_dir)] == {"added": True, "enabled": False}

        assert http.post("/api/v1/apps/add", json={"path": ext_dir}).status_code == 409  # already added
        assert http.post("/api/v1/apps/add", json={"path": clash}).status_code == 409  # name taken
        for bad in (os.path.join(elsewhere, "missing"), no_manifest, broken, "relative/dir"):
            resp = http.post("/api/v1/apps/add", json={"path": bad})
            assert resp.status_code == 400, (bad, resp.text)
        assert http.post("/api/v1/apps/add", json={}).status_code == 422

        # Rescans keep it, and it can be enabled and started like any app
        assert client.call("apps.reload")["removed"] == []
        assert http.put("/api/v1/apps/ext/enabled", json={"enabled": True}).status_code == 200
        assert http.post("/api/v1/apps/ext/start").status_code == 200
        _wait_until(lambda: client.call("apps.info", {"name": "ext"})["status"] == "running")

    # A new registry loads it from the settings; a vanished directory is skipped
    registry = AppRegistry([])
    registry.reload()
    assert registry.names() == ["ext"] and registry.require("ext").enabled is True
    shutil.rmtree(ext_dir)
    registry.reload()
    assert registry.names() == []


def test_manifest_versions():
    manifest = GeeAppManifest(name="a", title="A")
    assert (manifest.manifest_version, manifest.version) == ("1", "0.0.0")
    manifest = GeeAppManifest.model_validate({"name": "a", "title": "A", "manifest_version": 1, "version": "1.2.0"})
    assert (manifest.manifest_version, manifest.version) == ("1", "1.2.0")
    for field in ("manifest_version", "version"):
        with pytest.raises(pydantic.ValidationError):
            GeeAppManifest.model_validate({"name": "a", "title": "A", field: None})
    # The title is required
    with pytest.raises(pydantic.ValidationError):
        GeeAppManifest.model_validate({"name": "a"})
