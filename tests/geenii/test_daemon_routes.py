import pytest
from fastapi.testclient import TestClient

from geenii.server import daemon_routes
from geenii.server.server import app


class FakeDaemonClient:
    def __init__(self, available=True, info=None, info_error=None):
        self.socket_path = "/tmp/fake-geenii.sock"
        self._available = available
        self._info = info or {}
        self._info_error = info_error

    def is_available(self):
        return self._available

    def info(self):
        if self._info_error:
            raise self._info_error
        return self._info


@pytest.fixture
def make_client():
    def _make(fake):
        app.dependency_overrides[daemon_routes.dep_daemon_client] = lambda: fake
        return TestClient(app)

    yield _make
    app.dependency_overrides.pop(daemon_routes.dep_daemon_client, None)


def test_status_running(make_client):
    info = {"pid": 123, "uptime_s": 4.2, "pm": {"running": 1}}
    resp = make_client(FakeDaemonClient(info=info)).get("/api/v1/daemon/status")
    assert resp.status_code == 200
    assert resp.json() == {"running": True, "socket": "/tmp/fake-geenii.sock", "info": info, "error": None}


def test_status_not_running(make_client):
    resp = make_client(FakeDaemonClient(available=False)).get("/api/v1/daemon/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["running"] is False
    assert body["info"] is None
    assert "not running" in body["error"]


def test_status_info_fails(make_client):
    fake = FakeDaemonClient(info_error=ConnectionRefusedError("gone"))
    body = make_client(fake).get("/api/v1/daemon/status").json()
    assert body["running"] is False
    assert body["error"] == "gone"
