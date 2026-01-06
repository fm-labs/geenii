import os
import json
import pydantic
from pydantic import ConfigDict

from geenii.settings import DATA_DIR

BUILTIN_AGENTS = {}

class AgentConfigModelSettings(pydantic.BaseModel):
    model_config = {
        "extra": "allow",
        "json_schema_extra": {
            "example": {
                "debug": False,
                "mode": "benchmarks"
            }
        }
    }

    temperature: float | None = 0.7
    top_p: float | None = 1.0
    max_tokens: int | None = 2048


class AgentConfig(pydantic.BaseModel):
    id: str
    name: str
    description: str | None = None
    model: str | None = None
    model_settings: AgentConfigModelSettings = AgentConfigModelSettings()
    system_prompt: str | None = None
    tools: list[str] = pydantic.Field(default_factory=list)


def agent_config_from_json(data: dict) -> AgentConfig | None:
    try:
        return AgentConfig.model_validate(data)
    except pydantic.ValidationError as e:
        print("Agent definition validation error:", e)
        #raise ValueError(f"Invalid agent definition: {e}")
        return None


def get_agent_config(agentname: str) -> AgentConfig:
    """
    Retrieve an agent by name.
    Lookup the in the predefined agents list.
    Fallback to json definition file if not found.
    :param agentname:
    :return:
    """
    if not agentname or agentname.strip() == "":
        raise ValueError("No agent name provided.")

    if agentname in BUILTIN_AGENTS:
        return agent_config_from_json(BUILTIN_AGENTS[agentname])

    agent_file = f"{DATA_DIR}/wizards/{agentname}.wizard.json"
    if not os.path.exists(agent_file):
        raise FileNotFoundError(f"Agent definition file '{agent_file}' not found.")

    agent_json = None
    with open(agent_file, 'r') as f:
        agent_json = json.load(f)
    return agent_config_from_json(agent_json)