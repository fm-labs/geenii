import json

import pytest
from fastapi.testclient import TestClient

from geenii import mcp_config
from geenii.server.server import app

MASKED = "********"


@pytest.fixture
def root_file(mcp_dirs):
    root, _ = mcp_dirs
    root.parent.mkdir(parents=True)
    root.write_text(
        json.dumps(
            {
                "env": {"TOKEN": "abc"},
                "mcpServers": {
                    "local": {
                        "command": "echo",
                        "args": ["hi"],
                        "env": {"API_KEY": "secret"},
                        "cwd": "/tmp",
                    },
                    "remote": {
                        "url": "http://h/mcp",
                        "headers": {"Authorization": "Bearer ${TOKEN}"},
                    },
                },
            }
        )
    )
    return root


@pytest.fixture
def project_file(mcp_dirs):
    _, project = mcp_dirs
    project.parent.mkdir(parents=True)
    project.write_text(json.dumps({"mcpServers": {"project_only": {"command": "p"}}}))
    return project


@pytest.fixture
def client(root_file):
    # no `with`: the app's lifespan (which discovers all MCP servers' tools) is not run
    return TestClient(app)


def stored(root_file):
    return json.loads(root_file.read_text())["mcpServers"]


# ---------- list / config ----------


def test_list_masks_env(client):
    servers = {s["name"]: s for s in client.get("/api/v1/mcp/servers").json()}
    assert servers["local"] == {
        "name": "local",
        "type": "stdio",
        "url": None,
        "command": "echo",
        "args": ["hi"],
        "env": {"API_KEY": MASKED},
    }
    assert servers["remote"]["type"] == "http"
    assert "headers" not in servers["remote"]


def test_config_masks_env_and_headers(client):
    assert client.get("/api/v1/mcp/servers/local/config").json() == {
        "command": "echo",
        "args": ["hi"],
        "env": {"API_KEY": MASKED},
        "cwd": "/tmp",
    }
    assert client.get("/api/v1/mcp/servers/remote/config").json() == {
        "url": "http://h/mcp",
        "headers": {"Authorization": MASKED},
    }


def test_config_of_unknown_server_is_404(client):
    assert client.get("/api/v1/mcp/servers/nope/config").status_code == 404


# ---------- create ----------


def test_create(client, root_file):
    response = client.post(
        "/api/v1/mcp/servers",
        json={
            "name": "new-server_1",
            "config": {
                "url": "http://x/${TOKEN}",
                "headers": {"X-Key": "k"},
            },
        },
    )

    assert response.status_code == 201
    assert response.json()["name"] == "new-server_1"
    # written as sent, placeholders kept
    assert stored(root_file)["new-server_1"] == {
        "url": "http://x/${TOKEN}",
        "headers": {"X-Key": "k"},
    }
    assert "new-server_1" in [
        s["name"] for s in client.get("/api/v1/mcp/servers").json()
    ]


def test_create_existing_name_is_409(client, root_file):
    response = client.post(
        "/api/v1/mcp/servers", json={"name": "local", "config": {"command": "x"}}
    )
    assert response.status_code == 409
    assert stored(root_file)["local"]["command"] == "echo"


def test_create_name_taken_in_project_file_is_409(client, project_file):
    response = client.post(
        "/api/v1/mcp/servers", json={"name": "project_only", "config": {"command": "x"}}
    )
    assert response.status_code == 409


@pytest.mark.parametrize("name", ["", "with space", "slash/name", "dot.name", "ümlaut"])
def test_create_invalid_name_is_400(client, name):
    response = client.post(
        "/api/v1/mcp/servers", json={"name": name, "config": {"command": "x"}}
    )
    assert response.status_code == 400


@pytest.mark.parametrize(
    "config",
    [
        {},
        {"cwd": "/tmp"},
        {"command": "x", "args": "not a list"},
        {"command": "x", "args": ["ok", 1]},
        {"command": "x", "env": ["A=b"]},
        {"command": "x", "env": {"A": 1}},
        {"url": "http://x", "headers": {"A": None}},
    ],
)
def test_create_invalid_config_is_400(client, root_file, config):
    response = client.post(
        "/api/v1/mcp/servers", json={"name": "bad", "config": config}
    )
    assert response.status_code == 400
    assert "bad" not in stored(root_file)


def test_create_with_masked_value_is_400(client, root_file):
    response = client.post(
        "/api/v1/mcp/servers",
        json={"name": "bad", "config": {"command": "x", "env": {"A": MASKED}}},
    )
    assert response.status_code == 400
    assert "bad" not in stored(root_file)


# ---------- update ----------


def test_update_keeps_masked_values(client, root_file):
    response = client.put(
        "/api/v1/mcp/servers/local",
        json={
            "command": "cat",
            "env": {"API_KEY": MASKED, "NEW": "n"},
        },
    )

    assert response.status_code == 200
    assert response.json()["command"] == "cat"
    # keys left out (args, cwd) are removed
    assert stored(root_file)["local"] == {
        "command": "cat",
        "env": {"API_KEY": "secret", "NEW": "n"},
    }


def test_update_keeps_masked_header_with_placeholder(client, root_file):
    client.put(
        "/api/v1/mcp/servers/remote",
        json={"url": "http://h2/mcp", "headers": {"Authorization": MASKED}},
    )
    assert stored(root_file)["remote"] == {
        "url": "http://h2/mcp",
        "headers": {"Authorization": "Bearer ${TOKEN}"},
    }


def test_update_replaces_value_and_removes_left_out_key(client, root_file):
    client.put(
        "/api/v1/mcp/servers/local",
        json={"command": "echo", "env": {"API_KEY": "changed"}},
    )
    client.put("/api/v1/mcp/servers/remote", json={"url": "http://h/mcp"})
    assert stored(root_file)["local"]["env"] == {"API_KEY": "changed"}
    assert stored(root_file)["remote"] == {"url": "http://h/mcp"}


def test_update_with_unknown_masked_key_is_400(client, root_file):
    response = client.put(
        "/api/v1/mcp/servers/local", json={"command": "echo", "env": {"OTHER": MASKED}}
    )
    assert response.status_code == 400
    assert stored(root_file)["local"]["command"] == "echo"


def test_update_invalid_config_is_400(client, root_file):
    assert client.put("/api/v1/mcp/servers/local", json={"env": {}}).status_code == 400
    assert stored(root_file)["local"]["command"] == "echo"


def test_update_unknown_server_is_404(client, root_file):
    assert (
        client.put("/api/v1/mcp/servers/nope", json={"command": "x"}).status_code == 404
    )
    assert "nope" not in stored(root_file)


def test_update_project_only_server_is_409(client, project_file):
    assert (
        client.put(
            "/api/v1/mcp/servers/project_only", json={"command": "x"}
        ).status_code
        == 409
    )
    assert json.loads(project_file.read_text())["mcpServers"]["project_only"] == {
        "command": "p"
    }


def test_update_drops_cached_client(client):
    class FakeClient:
        closed = False

        def close(self):
            self.closed = True

    fake = FakeClient()
    mcp_config._client_cache["local"] = fake

    client.put("/api/v1/mcp/servers/local", json={"command": "cat"})

    assert fake.closed
    assert "local" not in mcp_config._client_cache


# ---------- delete ----------


def test_delete(client, root_file):
    response = client.delete("/api/v1/mcp/servers/local")

    assert response.status_code == 204
    assert response.content == b""
    assert set(stored(root_file)) == {"remote"}
    assert client.get("/api/v1/mcp/servers/local/config").status_code == 404


def test_delete_unknown_server_is_404(client):
    assert client.delete("/api/v1/mcp/servers/nope").status_code == 404


def test_delete_project_only_server_is_409(client, project_file):
    assert client.delete("/api/v1/mcp/servers/project_only").status_code == 409
    assert "project_only" in json.loads(project_file.read_text())["mcpServers"]
