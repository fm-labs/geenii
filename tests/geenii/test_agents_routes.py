import pytest
from fastapi.testclient import TestClient

from geenii.agent.registry import AgentRegistry, AgentSpec
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
    assert response.json() == [
        {"command": "clear", "description": "Clear the conversation memory"},
        {"command": "compact", "description": "Summarize and compact the conversation memory"},
        # sorted; broken and missing skills are skipped, "clear" stays the built-in command
        {"command": "notes", "description": "Take notes"},
        {"command": "weather", "description": "Get the weather forecast"},
    ]


def test_agent_without_skills_has_builtin_commands(client):
    commands = client.get("/api/v1/agents/plain/commands").json()
    assert [c["command"] for c in commands] == ["clear", "compact"]


def test_unknown_agent_is_404(client):
    response = client.get("/api/v1/agents/nope/commands")
    assert response.status_code == 404
    assert "nope" in response.json()["detail"]
