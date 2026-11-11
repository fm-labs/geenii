import json
import os

import pytest
from fastapi.testclient import TestClient

from geenii.server import daemon_routes, scheduler_routes
from geenii.server.server import app


class FakeDaemonClient:
    socket_path = "/tmp/fake-geenii.sock"

    def __init__(self, status=None, config=None):
        self._status = status
        self._config = config
        self.calls = []
        self.run_error = None

    def is_available(self):
        return self._status is not None

    def info(self):
        return {"scheduler": {"config": self._config}}

    def call(self, method, params=None):
        self.calls.append(method)
        if method == "scheduler.reload":
            return {"added": [], "removed": [], "updated": []}
        if method == "scheduler.run":
            if self.run_error:
                raise self.run_error
            return "started"
        assert method == "scheduler.status"
        return self._status


@pytest.fixture
def api(tmp_path):
    """(TestClient, default config path) with no daemon running, unless a fake is passed."""
    default_path = str(tmp_path / "scheduler.json")

    def _api(fake=None):
        fake = fake or FakeDaemonClient()
        app.dependency_overrides[daemon_routes.dep_daemon_client] = lambda: fake
        app.dependency_overrides[scheduler_routes.dep_scheduler_config_path] = lambda: default_path
        return TestClient(app)

    yield _api, default_path
    app.dependency_overrides.clear()


@pytest.fixture
def get_config(tmp_path):
    default_path = str(tmp_path / "scheduler.json")

    def _get(fake):
        app.dependency_overrides[daemon_routes.dep_daemon_client] = lambda: fake
        app.dependency_overrides[scheduler_routes.dep_scheduler_config_path] = lambda: default_path
        return TestClient(app).get("/api/v1/scheduler/config")

    yield _get, default_path
    app.dependency_overrides.clear()


def _write(path, tasks):
    with open(path, "w") as f:
        json.dump({"tasks": tasks}, f)


def test_missing_config_without_daemon(get_config):
    get, path = get_config
    body = get(FakeDaemonClient()).json()
    assert body["path"] == path
    assert body["exists"] is False
    assert body["daemon"]["running"] is False
    assert body["tasks"] == []
    assert body["error"] is None


def test_config_without_daemon(get_config):
    get, path = get_config
    _write(
        path,
        [
            {"name": "a", "interval": "cron:* * * * *", "cmd": ["echo", "a"]},
            {"name": "b", "interval": "every:5m", "module": "x.y", "enabled": False},
        ],
    )
    body = get(FakeDaemonClient()).json()
    assert [t["name"] for t in body["tasks"]] == ["a", "b"]
    assert body["tasks"][0]["enabled"] is True
    assert body["tasks"][1]["enabled"] is False
    assert all(t["live"] is None for t in body["tasks"])


def test_config_merges_live_state(get_config, tmp_path):
    get, _ = get_config
    daemon_path = str(tmp_path / "daemon-scheduler.json")
    _write(
        daemon_path,
        [
            {"name": "a", "interval": "cron:* * * * *", "cmd": ["echo", "a"]},
            {"name": "off", "interval": "cron:* * * * *", "cmd": ["true"], "enabled": False},
        ],
    )
    live_a = {
        "name": "a",
        "interval": "cron:* * * * *",
        "cmd": ["echo", "a"],
        "module": None,
        "next_run": "2026-01-01T00:01:00+00:00",
        "last_run": None,
        "running": False,
        "last_run_id": None,
        "enabled": True,
    }
    live_extra = {**live_a, "name": "added", "cmd": ["echo", "added"]}
    status = {"status": "running", "tasks": [live_a, live_extra]}

    body = get(FakeDaemonClient(status=status, config=daemon_path)).json()
    assert body["path"] == daemon_path
    assert body["daemon"] == {"running": True, "config": daemon_path, "status": "running", "error": None}
    tasks = {t["name"]: t for t in body["tasks"]}
    assert tasks["a"]["live"] == live_a
    assert tasks["off"]["live"] is None
    assert tasks["added"]["not_in_config"] is True


def test_invalid_json(get_config):
    get, path = get_config
    with open(path, "w") as f:
        f.write("{not json")
    body = get(FakeDaemonClient()).json()
    assert body["exists"] is True
    assert body["tasks"] == []
    assert "Could not read" in body["error"]


def _read(path):
    with open(path) as f:
        return json.load(f)["tasks"]


TASK = {"name": "hello", "interval": "cron:*/5 * * * *", "cmd": ["echo", "hi"]}


def test_create_task_writes_file(api):
    make, path = api
    resp = make().post("/api/v1/scheduler/tasks", json={**TASK, "timeout": 30, "env": {"A": "1"}})
    assert resp.status_code == 201
    assert resp.json()["reload"]["reloaded"] is False
    assert _read(path) == [
        {
            "enabled": True,
            "name": "hello",
            "interval": "cron:*/5 * * * *",
            "cmd": ["echo", "hi"],
            "env": {"A": "1"},
            "timeout": 30,
        }
    ]


def test_create_duplicate_conflicts(api):
    make, _ = api
    client = make()
    assert client.post("/api/v1/scheduler/tasks", json=TASK).status_code == 201
    assert client.post("/api/v1/scheduler/tasks", json=TASK).status_code == 409


@pytest.mark.parametrize(
    "body, message",
    [
        ({**TASK, "interval": "every 5m"}, "Invalid interval"),
        ({**TASK, "interval": "cron:not a cron"}, "Invalid cron"),
        ({**TASK, "module": "pkg.fn"}, "either a command or a module"),
        ({"name": "x", "interval": "cron:* * * * *"}, "either a command or a module"),
        ({"name": "x", "interval": "cron:* * * * *", "module": "nodot"}, "at least one dot"),
        ({**TASK, "name": "  "}, "Name"),
    ],
)
def test_create_invalid(api, body, message):
    make, path = api
    resp = make().post("/api/v1/scheduler/tasks", json=body)
    assert resp.status_code == 400
    assert message in resp.text
    assert not os.path.exists(path)


def test_update_and_rename_keeps_unknown_keys(api):
    make, path = api
    with open(path, "w") as f:
        json.dump(
            {"tasks": [{**TASK, "note": "keep me"}, {"name": "other", "interval": "cron:* * * * *", "cmd": ["true"]}]},
            f,
        )
    body = {
        "name": "renamed",
        "interval": "at:2030-01-01T10:00:00+00:00",
        "module": "pkg.fn",
        "params": ["a"],
        "enabled": False,
    }
    resp = make().put("/api/v1/scheduler/tasks/hello", json=body)
    assert resp.status_code == 200
    tasks = _read(path)
    assert tasks[0] == {
        "enabled": False,
        "name": "renamed",
        "interval": "at:2030-01-01T10:00:00+00:00",
        "module": "pkg.fn",
        "params": ["a"],
        "note": "keep me",
    }
    assert tasks[1]["name"] == "other"


def test_update_errors(api):
    make, path = api
    with open(path, "w") as f:
        json.dump({"tasks": [TASK, {**TASK, "name": "other"}]}, f)
    client = make()
    assert client.put("/api/v1/scheduler/tasks/missing", json=TASK).status_code == 404
    assert client.put("/api/v1/scheduler/tasks/hello", json={**TASK, "name": "other"}).status_code == 409


def test_delete_task(api):
    make, path = api
    with open(path, "w") as f:
        json.dump({"tasks": [TASK]}, f)
    client = make()
    assert client.delete("/api/v1/scheduler/tasks/hello").status_code == 200
    assert _read(path) == []
    assert client.delete("/api/v1/scheduler/tasks/hello").status_code == 404


def test_write_reloads_daemon_using_the_file(api, tmp_path):
    make, default_path = api
    daemon_path = str(tmp_path / "daemon.json")
    fake = FakeDaemonClient(status={"status": "running", "tasks": []}, config=daemon_path)
    resp = make(fake).post("/api/v1/scheduler/tasks", json=TASK)
    assert resp.status_code == 201
    assert resp.json()["path"] == daemon_path
    assert resp.json()["reload"]["reloaded"] is True
    assert fake.calls == ["scheduler.reload"]
    assert _read(daemon_path)[0]["name"] == "hello"
    assert not os.path.exists(default_path)


def test_invalid_file_is_not_overwritten(api):
    make, path = api
    with open(path, "w") as f:
        f.write("{broken")
    assert make().post("/api/v1/scheduler/tasks", json=TASK).status_code == 409
    with open(path) as f:
        assert f.read() == "{broken"


def test_run_task_in_daemon(api, tmp_path):
    make, _ = api
    fake = FakeDaemonClient(status={"status": "running", "tasks": []}, config=str(tmp_path / "d.json"))
    resp = make(fake).post("/api/v1/scheduler/tasks/hello/run")
    assert resp.status_code == 202
    assert resp.json()["status"] == "started"
    assert fake.calls == ["scheduler.run"]


def test_run_task_without_daemon(api):
    make, _ = api
    assert make().post("/api/v1/scheduler/tasks/hello/run").status_code == 409


@pytest.mark.parametrize(
    "error, status",
    [
        (RuntimeError("KeyError: 'Unknown task: hello'"), 404),
        (RuntimeError("RuntimeError: Task 'hello' is already running"), 409),
        (ConnectionRefusedError("refused"), 503),
    ],
)
def test_run_task_errors(api, tmp_path, error, status):
    make, _ = api
    fake = FakeDaemonClient(status={"status": "running", "tasks": []}, config=str(tmp_path / "d.json"))
    fake.run_error = error
    resp = make(fake).post("/api/v1/scheduler/tasks/hello/run")
    assert resp.status_code == status
    if status == 409:
        assert resp.json()["detail"] == "Task 'hello' is already running"
