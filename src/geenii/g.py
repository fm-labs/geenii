from __future__ import annotations

import os

from geenii.agent.registry import AgentRegistry, AgentSpec, init_agent
from geenii.ai import enumerate_providers, enumerate_models
from geenii.bots import BotInterface
from geenii.config import GEENII_DIR, APP_VERSION, DEFAULT_COMPLETION_MODEL, \
    CACHE_DIR, GEENII_WORKING_DIR
from geenii.skills import SkillRegistry, skill_paths
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


def makedirs_safe(path: str):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        print(f"Error creating directory {path}: {e}")

def make_app_directories():
    # ensure internal directories exist
    makedirs_safe(f"{CACHE_DIR}")
    makedirs_safe(f"{CACHE_DIR}/logs")


def agent_paths():
    return [
        f"{get_user_home_dir()}/.geenii/agents",
        f"{GEENII_WORKING_DIR}/.geenii/agents",
        f"{GEENII_DIR}/agents",
    ]


def init_global_agent_registry() -> AgentRegistry:
    _agents = AgentRegistry()
    # default
    _agents._agent_configs.update({"default": AgentSpec(
        name="default",
        model=DEFAULT_COMPLETION_MODEL or "ollama:qwen3:8b"

    )})
    for agent_dir in agent_paths():
        _agents.load_from_directory(agent_dir)
    return _agents


def locate_agent_md_file(agent_name: str) -> str|None:
    for agent_dir in agent_paths():
        md_file_path = f"{agent_dir}/{agent_name}.md"
        if os.path.exists(md_file_path):
            return md_file_path
    return None

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
    md_file_path = locate_agent_md_file(name)
    if md_file_path is None:
        raise ValueError(f"Agent '{name}' not found.")

    try:
        agent_conf = AgentSpec.from_md_file(md_file_path)
        return init_agent(agent_conf)
    except Exception as e:
        raise e


def init_global_skill_registry() -> SkillRegistry:
    skill_reg = SkillRegistry()
    for skill_path in skill_paths():
        skill_reg.register_all_from_directory(skill_path)
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
            "geenii_dir": GEENII_DIR,
            "cache_dir": CACHE_DIR,
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