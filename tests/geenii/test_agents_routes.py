import pytest
from fastapi.testclient import TestClient

from geenii.agent.registry import AgentRegistry, AgentSpec
from geenii.agents import Agent
from geenii.server import agents_routes
from geenii.server.server import app
from geenii.skills import SkillSpec


class FakeSkillRegistry:
    SKILLS = {
        "weather": SkillSpec(name="weather", description="Get the weather forecast", path="/tmp/weather"),
        "notes": SkillSpec(name="notes", description="Take notes", path="/tmp/notes"),
        "clear": SkillSpec(name="clear", description="A skill shadowed by the built-in command", path="/tmp/clear"),
    }

    def load(self, name):
        if name == "broken":
            raise ValueError("Malformed skill markdown file")
        return self.SKILLS.get(name)


@pytest.fixture
def client(monkeypatch):
    agents = AgentRegistry()
    agents.configs.update({
        "default": AgentSpec(name="default", model="fake:test", skills=["weather", "broken", "missing", "notes", "clear"]),
        "plain": AgentSpec(name="plain", model="fake:test"),
    })
    monkeypatch.setattr(agents_routes, "SkillRegistry", FakeSkillRegistry)
    app.dependency_overrides[agents_routes.dep_agent_registry] = lambda: agents
    yield TestClient(app)
    app.dependency_overrides.pop(agents_routes.dep_agent_registry, None)


def test_commands_are_builtins_then_skills(client):
    response = client.get("/api/v1/agents/default/commands")

    assert response.status_code == 200
    builtins = [{"command": c, "description": d} for c, d in Agent.BUILTIN_COMMANDS.items()]
    assert response.json() == builtins + [
        # sorted; broken and missing skills are skipped, "clear" stays the built-in command
        {"command": "notes", "description": "Take notes"},
        {"command": "weather", "description": "Get the weather forecast"},
    ]


def test_agent_without_skills_has_builtin_commands(client):
    commands = client.get("/api/v1/agents/plain/commands").json()
    names = [c["command"] for c in commands]
    assert names == list(Agent.BUILTIN_COMMANDS)
    assert names[:2] == ["clear", "compact"]
    assert {"self", "usage", "models", "tools", "context", "help"} <= set(names)


def test_unknown_agent_is_404(client):
    response = client.get("/api/v1/agents/nope/commands")
    assert response.status_code == 404
    assert "nope" in response.json()["detail"]


@pytest.fixture
def agent_dirs(tmp_path, monkeypatch):
    dirs = {scope: tmp_path / scope for scope in ("project", "user", "global")}
    monkeypatch.setattr(agents_routes, "agent_paths", lambda: [(str(d), s) for s, d in dirs.items()])
    return dirs


@pytest.fixture
def write_client(agent_dirs):
    agents = AgentRegistry()
    agents.configs.update({"builtin": AgentSpec(name="builtin", model="fake:test", scope="global")})
    app.dependency_overrides[agents_routes.dep_agent_registry] = lambda: agents
    yield TestClient(app), agents
    app.dependency_overrides.pop(agents_routes.dep_agent_registry, None)


SPEC = {
    "name": "news",
    "model": "ollama:qwen3:8b",
    "label": "News: HN",
    "description": "Fetches news.\nUse for \"what is trending\".",
    "model_parameters": {"temperature": 0.7, "stop": ["a", "b"]},
    "mcp_servers": ["hackernews"],
    "tools": ["mcp__hackernews__get_stories", "-x"],
    "skills": [],
}


def test_create_writes_file_and_registers(write_client, agent_dirs):
    client, agents = write_client
    response = client.post("/api/v1/agents/", json={"spec": SPEC, "instructions": "# News\n\nBe brief.", "scope": "project"})

    assert response.status_code == 201
    path = agent_dirs["project"] / "news.md"
    assert response.json()["file_path"] == str(path)
    assert response.json()["instructions"] == "# News\n\nBe brief."
    loaded = AgentSpec.from_md_file(str(path))
    assert loaded.label == "News: HN"
    assert loaded.description == SPEC["description"]
    assert loaded.model_parameters == {"temperature": 0.7, "stop": ["a", "b"]}
    assert loaded.tools == SPEC["tools"]
    assert "skills" not in path.read_text()  # empty values are left out
    assert agents.get_config("news").scope == "project"
    assert client.get("/api/v1/agents/news").status_code == 200


def test_create_existing_agent_is_409(write_client):
    client, _ = write_client
    response = client.post("/api/v1/agents/", json={"spec": {**SPEC, "name": "builtin"}})
    assert response.status_code == 409


def test_create_over_existing_file_is_409(write_client, agent_dirs):
    client, _ = write_client
    agent_dirs["user"].mkdir()
    (agent_dirs["user"] / "news.md").write_text("---\nname: other\nmodel: x:y\n---\n")
    assert client.post("/api/v1/agents/", json={"spec": SPEC}).status_code == 409


@pytest.mark.parametrize("name", ["", "has space", "../escape", "a/b"])
def test_create_invalid_name_is_400(write_client, name):
    client, _ = write_client
    assert client.post("/api/v1/agents/", json={"spec": {**SPEC, "name": name}}).status_code == 400


def test_create_rejects_load_time_fields(write_client):
    client, _ = write_client
    response = client.post("/api/v1/agents/", json={"spec": {**SPEC, "file_path": "/etc/passwd"}})
    assert response.status_code == 422


def test_update_rewrites_file(write_client, agent_dirs):
    client, agents = write_client
    client.post("/api/v1/agents/", json={"spec": SPEC, "instructions": "old"})

    response = client.put("/api/v1/agents/news", json={"spec": {**SPEC, "model": "openai:gpt-4o", "tools": []}, "instructions": "new"})

    assert response.status_code == 200
    loaded = AgentSpec.from_md_file(str(agent_dirs["user"] / "news.md"))
    assert loaded.model == "openai:gpt-4o"
    assert loaded.tools == []
    assert loaded.instructions == "new"
    assert agents.get_config("news").model == "openai:gpt-4o"
    assert agents.get_config("news").scope == "user"


def test_update_builtin_agent_creates_user_file(write_client, agent_dirs):
    client, agents = write_client
    response = client.put("/api/v1/agents/builtin", json={"spec": {"name": "builtin", "model": "fake:other"}})

    assert response.status_code == 200
    assert (agent_dirs["user"] / "builtin.md").is_file()
    assert agents.get_config("builtin").scope == "user"
    assert agents.get_config("builtin").model == "fake:other"


def test_update_unknown_agent_is_404(write_client):
    client, _ = write_client
    assert client.put("/api/v1/agents/nope", json={"spec": {**SPEC, "name": "nope"}}).status_code == 404


def test_update_rename_is_400(write_client):
    client, _ = write_client
    client.post("/api/v1/agents/", json={"spec": SPEC})
    assert client.put("/api/v1/agents/news", json={"spec": {**SPEC, "name": "other"}}).status_code == 400
