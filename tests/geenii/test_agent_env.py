import os
import stat

import pytest
from fastapi.testclient import TestClient

from geenii import tools
from geenii.agent.env import AgentEnvStore
from geenii.agent.registry import AgentRegistry, AgentSpec
from geenii.server import agents_routes
from geenii.server.server import app
from geenii.tool.common import Tool, ToolCallResult


@pytest.fixture
def store(tmp_path):
    return AgentEnvStore(tmp_path)


def test_vars_and_secrets_round_trip(store):
    values = {"PLAIN": "abc", "SPACES": "a b c", "QUOTE": "it's \"quoted\"", "HASH": "x # y", "MULTI": "line1\nline2", "EMPTY": ""}
    store.set_vars("bot", values)
    assert store.get_vars("bot") == values

    store.set_secret("bot", "API_KEY", "s3cr3t'$HOME")
    assert store.get_secrets("bot") == {"API_KEY": "s3cr3t'$HOME"}
    assert store.secret_keys("bot") == ["API_KEY"]


def test_files_are_separate_and_secrets_private(store):
    store.set_var("bot", "A", "1")
    store.set_secret("bot", "B", "2")
    assert store.vars_path("bot").read_text() == "A='1'\n"
    assert store.secrets_path("bot").read_text() == "B='2'\n"
    assert stat.S_IMODE(os.stat(store.secrets_path("bot")).st_mode) == 0o600


def test_resolve_secrets_win(store):
    store.set_vars("bot", {"A": "var", "B": "var"})
    store.set_secret("bot", "B", "secret")
    assert store.resolve("bot") == {"A": "var", "B": "secret"}
    assert store.resolve("other") == {}


def test_delete_removes_empty_files(store):
    store.set_secret("bot", "B", "2")
    assert store.delete_secret("bot", "B") is True
    assert store.delete_secret("bot", "B") is False
    assert not store.secrets_path("bot").exists()


def test_invalid_keys_are_rejected(store):
    with pytest.raises(ValueError):
        store.set_var("bot", "1BAD", "x")
    with pytest.raises(ValueError):
        store.set_secret("bot", "BAD-KEY", "x")


class EnvEchoTool(Tool):
    def __init__(self):
        super().__init__("env_echo", "", {})
        self.seen_env = None

    def invoke(self, args, env=None, **kwargs):
        self.seen_env = dict(env)
        return ToolCallResult(text="ok")


def test_invoke_tool_passes_secrets_and_redacts_logs(monkeypatch):
    logged = {}
    monkeypatch.setattr(tools, "append_jsonl", lambda path, data: logged.update(data))
    tool = EnvEchoTool()
    env = {"MY_PASSWORD": "pw", "SERVICE": "sv", "PLAIN": "p"}

    tools.invoke_tool(tool, args={}, env=env, secret_keys={"SERVICE"})

    assert tool.seen_env == {"MY_PASSWORD": "pw", "SERVICE": "sv", "PLAIN": "p"}
    assert env == {"MY_PASSWORD": "pw", "SERVICE": "sv", "PLAIN": "p"}
    assert logged["env"] == {"MY_PASSWORD": "REDACTED", "SERVICE": "REDACTED", "PLAIN": "p"}


@pytest.fixture
def client(store):
    agents = AgentRegistry()
    agents.configs.update({"bot": AgentSpec(name="bot", model="fake:test")})
    app.dependency_overrides[agents_routes.dep_agent_registry] = lambda: agents
    app.dependency_overrides[agents_routes.dep_agent_env_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.pop(agents_routes.dep_agent_registry, None)
    app.dependency_overrides.pop(agents_routes.dep_agent_env_store, None)


def test_env_routes_never_return_secret_values(client, store):
    assert client.get("/api/v1/agents/bot/env").json() == {"vars": {}, "secrets": []}

    response = client.put("/api/v1/agents/bot/env/vars", json={"REGION": "eu"})
    assert response.json() == {"vars": {"REGION": "eu"}, "secrets": []}

    response = client.put("/api/v1/agents/bot/env/secrets/TOKEN", json={"value": "t0k3n"})
    assert response.json() == {"vars": {"REGION": "eu"}, "secrets": ["TOKEN"]}
    assert "t0k3n" not in client.get("/api/v1/agents/bot/env").text
    assert store.get_secrets("bot") == {"TOKEN": "t0k3n"}

    assert client.delete("/api/v1/agents/bot/env/secrets/TOKEN").json()["secrets"] == []
    assert client.delete("/api/v1/agents/bot/env/secrets/TOKEN").status_code == 404


def test_env_routes_validate(client):
    assert client.get("/api/v1/agents/nobody/env").status_code == 404
    assert client.put("/api/v1/agents/bot/env/vars", json={"BAD-KEY": "x"}).status_code == 400
    assert client.put("/api/v1/agents/bot/env/secrets/1BAD", json={"value": "x"}).status_code == 400


def test_init_agent_loads_env(monkeypatch, store):
    from geenii import g
    store.set_var("bot", "REGION", "eu")
    store.set_secret("bot", "TOKEN", "t0k3n")
    monkeypatch.setattr(g, "AgentEnvStore", lambda: store)

    agent = g.init_agent(AgentSpec(name="bot", model="fake:test"))

    assert agent.env == {"REGION": "eu", "TOKEN": "t0k3n"}
    assert agent.secret_keys == {"TOKEN"}
    assert "t0k3n" not in str(agent.to_dict())
