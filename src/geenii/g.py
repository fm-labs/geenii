from __future__ import annotations

import pydantic

from geenii.agent.registry import AgentRegistry, AgentSpec, init_agent
from geenii.chat.chat_bots import BotInterface
from geenii.config import USER_DIR
from geenii.skills import SkillRegistry
from geenii.utils.json_util import read_json


def get_bot(botname: str) -> BotInterface:
    # return EchoBot(botname=botname)
    # return SimpleBot(botname=botname)
    # return DemoAgent(botname=botname)

    if not botname.startswith("geenii:bot:"):
        raise ValueError(f"Invalid bot name: {botname}. Bot names must start with 'geenii:bot:'")

    name = botname[len("geenii:bot:"):]
    return init_agent_by_name(name)


def init_agent_registry(base_path: str = None, auto_load: bool = False) -> AgentRegistry:
    reg = AgentRegistry()
    if auto_load:
        reg.register_all_from_directory(f"{USER_DIR}/agents")
    return reg


def init_agent_by_name(name: str) -> "Agent":
    """
    Load a agent configuration from a JSON file and create a Agent instance.
    The JSON file should contain the following fields:
    - name: The name of the agent
    - model: (optional) The AI model to use for this agent
    - system: (optional) The system prompt to use for this agent
    - description: (optional) A description of the agent's purpose and capabilities
    - tools: (optional) A list of tool definitions that the agent can use
    - mcp_servers: (optional) A dictionary of MCP server configurations that the agent can connect to
    """
    file_path = f"{USER_DIR}/agents.json"

    data = read_json(file_path)
    if not isinstance(data, list):
        raise ValueError(f"Invalid agent configuration in {file_path}: expected a JSON list of BotConfig data.")

    config = next((item for item in data if item.get("name") == name), None)
    if config is None:
        raise ValueError(f"Agent configuration with name '{name}' not found in {file_path}.")

    try:
        agent_conf = AgentSpec.model_validate(config)
    except pydantic.ValidationError as e:
        raise ValueError(f"Invalid agent configuration in {file_path}: {str(e)}")
    return init_agent(agent_conf)


def init_skills() -> SkillRegistry:
    skill_reg = SkillRegistry()
    skill_reg.register_all_from_directory(f"{USER_DIR}/skills")
    skill_reg.register_all_from_directory(f"{USER_DIR}/vendor/skills/anthropic/skills")
    return skill_reg
