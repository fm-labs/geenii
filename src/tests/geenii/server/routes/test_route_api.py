from fastapi.testclient import TestClient

from server import app

client = TestClient(app)

def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_info():
    r = client.get("/api/info")
    assert r.status_code == 200
    assert r.json() == {"version": "0.1.0"}