import json

import pytest
from fastapi.testclient import TestClient

from geenii.server import daemon_helper, supervisor_routes
from geenii.server.server import app


class FakeDaemonClient:
    socket_path = "/tmp/fake-geeniid.sock"

    def __init__(self, status=None, config=None):
        self._status = status
        self._config = config
        self.calls = []
        self.error = None

    def is_available(self):
        return self._status is not None

    def info(self):
        return {"supervisor": {"config": self._config}}

    def call(self, method, params=None):
        self.calls.append((method, params))
        if self.error:
            raise self.error
        if method == "supervisor.reload":
            return {"started": [], "stopped": [], "restarted": []}
        if method == "supervisor.logs":
            return ["[supervisor] started pid=1", "[stdout] hello"]
        if method in ("supervisor.start", "supervisor.stop", "supervisor.restart"):
            return "ok"
        assert method == "supervisor.status"
        return self._status


EMPTY_STATUS = {"desired": {}, "running": {}, "watchers": {}}


def _desired(cmd, source="config", restart=True):
    return {"source": source, "cmd": cmd, "restart": restart, "cwd": None, "capture_output": True, "env_keys": []}


@pytest.fixture
def api(tmp_path):
    """(factory for a TestClient using a fake daemon, default config path)."""
    default_path = str(tmp_path / "services.json")

    def _api(fake=None):
        fake = fake or FakeDaemonClient()
        app.dependency_overrides[daemon_helper.dep_daemon_client] = lambda: fake
        app.dependency_overrides[supervisor_routes.dep_services_config_path] = lambda: default_path
        return TestClient(app)

    yield _api, default_path
    app.dependency_overrides.clear()


def _write(path, services):
    with open(path, "w") as f:
        json.dump({"services": services}, f)


def _read(path):
    with open(path) as f:
        return json.load(f)["services"]


def test_missing_config_without_daemon(api):
    make, path = api
    body = make().get("/api/v1/supervisor/config").json()
    assert body == {
        "path": path,
        "exists": False,
        "daemon": {"running": False, "config": None, "error": None},
        "services": [],
        "error": None,
    }


def test_config_merges_live_state(api, tmp_path):
    make, _ = api
    path = str(tmp_path / "daemon-services.json")
    _write(
        path,
        [
            {"name": "web", "cmd": ["python", "-m", "http.server"]},
            {"name": "backoff", "cmd": ["false"]},
            {"name": "kept", "cmd": ["sleep", "9"]},
            {"name": "off", "cmd": ["true"], "enabled": False},
        ],
    )
    status = {
        "desired": {
            "web": _desired(["python", "-m", "http.server"]),
            "backoff": _desired(["false"]),
            "kept": _desired(["sleep", "9"]),
            "adhoc": _desired(["sleep", "1"], source="api"),
        },
        "running": {
            "web": {"pid": 42, "returncode": None, "uptime_s": 3.0, "backoff_s": 0.5, "last_exit": None},
            "adhoc": {"pid": 43, "returncode": None, "uptime_s": 1.0, "backoff_s": 0.5, "last_exit": None},
        },
        "watchers": {
            "web": {"done": False, "cancelled": False, "task_name": "watch:web"},
            "backoff": {"done": False, "cancelled": False, "task_name": "watch:backoff"},
            "adhoc": {"done": False, "cancelled": False, "task_name": "watch:adhoc"},
        },
    }
    body = make(FakeDaemonClient(status, config=path)).get("/api/v1/supervisor/config").json()
    assert body["path"] == path
    assert body["daemon"]["running"] is True
    by_name = {s["name"]: s for s in body["services"]}
    assert by_name["web"]["live"]["state"] == "running"
    assert by_name["web"]["live"]["pid"] == 42
    assert by_name["backoff"]["live"]["state"] == "restarting"
    assert by_name["kept"]["live"]["state"] == "stopped"
    assert by_name["off"]["live"] is None
    assert by_name["off"]["enabled"] is False
    assert by_name["adhoc"]["not_in_config"] is True
    assert by_name["adhoc"]["live"]["source"] == "api"


def test_invalid_json(api):
    make, path = api
    with open(path, "w") as f:
        f.write("{nope")
    body = make().get("/api/v1/supervisor/config").json()
    assert body["exists"] is True
    assert "Could not read" in body["error"]
    # A broken file is never overwritten
    assert make().post("/api/v1/supervisor/services", json={"name": "a", "cmd": ["x"]}).status_code == 409


def test_create_update_delete(api):
    make, path = api
    client = make()
    res = client.post(
        "/api/v1/supervisor/services",
        json={"name": "web", "cmd": ["python", "-m", "http.server"], "restart": False, "env": {"A": "1"}},
    )
    assert res.status_code == 201
    assert res.json()["reload"] == {"reloaded": False, "changes": None, "error": None}
    assert _read(path) == [{"name": "web", "cmd": ["python", "-m", "http.server"], "restart": False, "env": {"A": "1"}}]

    assert client.post("/api/v1/supervisor/services", json={"name": "web", "cmd": ["x"]}).status_code == 409

    # Unknown keys of the entry are kept; rename
    _write(path, [{**_read(path)[0], "note": "keep me"}])
    res = client.put("/api/v1/supervisor/services/web", json={"name": "www", "cmd": ["srv"], "enabled": False})
    assert res.status_code == 200
    assert _read(path) == [{"name": "www", "cmd": ["srv"], "enabled": False, "note": "keep me"}]
    assert client.put("/api/v1/supervisor/services/nope", json={"name": "x", "cmd": ["x"]}).status_code == 404

    assert client.delete("/api/v1/supervisor/services/www").status_code == 200
    assert _read(path) == []
    assert client.delete("/api/v1/supervisor/services/www").status_code == 404


@pytest.mark.parametrize("body", [{"name": "a", "cmd": []}, {"name": "", "cmd": ["x"]}, {"name": "a", "cmd": [" "]}])
def test_create_invalid(api, body):
    make, _ = api
    assert make().post("/api/v1/supervisor/services", json=body).status_code in (400, 422)


def test_write_reloads_daemon_using_the_file(api, tmp_path):
    make, _ = api
    path = str(tmp_path / "daemon-services.json")
    fake = FakeDaemonClient(EMPTY_STATUS, config=path)
    res = make(fake).post("/api/v1/supervisor/services", json={"name": "a", "cmd": ["x"]})
    assert res.json()["path"] == path
    assert res.json()["reload"]["reloaded"] is True
    assert ("supervisor.reload", None) in fake.calls


@pytest.mark.parametrize(
    ("action", "method", "params"),
    [
        ("start", "supervisor.start", {"name": "web"}),
        ("stop", "supervisor.stop", {"name": "web", "disable_restart": False}),
        ("restart", "supervisor.restart", {"name": "web"}),
    ],
)
def test_control(api, action, method, params):
    make, _ = api
    fake = FakeDaemonClient(EMPTY_STATUS)
    assert make(fake).post(f"/api/v1/supervisor/services/web/{action}").status_code == 200
    assert (method, params) in fake.calls


def test_logs(api):
    make, _ = api
    res = make(FakeDaemonClient(EMPTY_STATUS)).get("/api/v1/supervisor/services/web/logs?tail=5")
    assert res.json() == {"name": "web", "lines": ["[supervisor] started pid=1", "[stdout] hello"]}


def test_control_without_daemon(api):
    make, _ = api
    assert make().post("/api/v1/supervisor/services/web/restart").status_code == 409
    assert make().get("/api/v1/supervisor/services/web/logs").status_code == 409


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (RuntimeError("KeyError: 'web'"), 404),
        (RuntimeError("ValueError: bad"), 400),
        (RuntimeError("RuntimeError: busy"), 409),
        (RuntimeError("Unknown method: x"), 500),
        (OSError("gone"), 503),
    ],
)
def test_control_errors(api, error, status):
    make, _ = api
    fake = FakeDaemonClient(EMPTY_STATUS)
    fake.error = error
    assert make(fake).post("/api/v1/supervisor/services/web/start").status_code == status


def test_failed_state_and_max_failures(api, tmp_path):
    make, _ = api
    path = str(tmp_path / "daemon-services.json")
    _write(path, [{"name": "web", "cmd": ["x"], "max_failures": 5}])
    status = {
        "desired": {
            "web": {**_desired(["x"]), "max_failures": 5, "failures": 5, "gave_up": {"failures": 5, "at": 1.0}}
        },
        "running": {},
        "watchers": {"web": {"done": True, "cancelled": False, "task_name": "watch:web"}},
    }
    (web,) = make(FakeDaemonClient(status, config=path)).get("/api/v1/supervisor/config").json()["services"]
    assert web["live"]["state"] == "failed"
    assert web["live"]["failures"] == 5 and web["max_failures"] == 5

    client = make()
    client.post("/api/v1/supervisor/services", json={"name": "a", "cmd": ["x"], "max_failures": 0})
    client.post("/api/v1/supervisor/services", json={"name": "b", "cmd": ["x"], "max_failures": 1000})
    _, default_path = api
    assert _read(default_path) == [{"name": "a", "cmd": ["x"], "max_failures": 0}, {"name": "b", "cmd": ["x"]}]
    assert (
        client.post("/api/v1/supervisor/services", json={"name": "c", "cmd": ["x"], "max_failures": -1}).status_code
        == 422
    )
