from __future__ import annotations

import os

import pydantic

from geenii.agent.registry import AgentRegistry, AgentSpec, init_agent
from geenii.ai import enumerate_providers, enumerate_models
from geenii.bots import BotInterface
from geenii.config import USER_DIR, APP_VERSION, get_data_dir
from geenii.skills import SkillRegistry
from geenii.utils.json_util import read_json
from geenii.utils.os_util import get_user_home_dir
from geenii.utils.system_util import get_system_report


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


def get_app_info() -> dict:
    allowed_env_vars = ["PATH", "HOME", "USER", "USERNAME"]

    ai_providers = enumerate_providers()
    ai_models = enumerate_models()

    data = dict({
        "app": {
            "version": APP_VERSION,
            "cwd": os.getcwd(),
            "user_home_dir": get_user_home_dir(),
            "data_dir": get_data_dir()
        },
        "config": {

        },
        "providers": [provier.model_dump() for provier in ai_providers],
        "models": [model.model_dump() for model in ai_models],
    })

    # add system report
    # if not in DEV_MODE, remove the env variables from the report for security reasons
    report = get_system_report()
    if not os.environ.get("DEV_MODE", "0") == "1":
        if "env" in report:
            report["env"] = {k: v for k, v in report["env"].items() if k in allowed_env_vars}
    data.update({"system": report})

    return data