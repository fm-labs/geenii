from __future__ import annotations

import os
from typing import TYPE_CHECKING

from geenii.agent.base import DEFAULT_AGENT_SYSTEM_PROMPT
from geenii.agent.registry import AgentRegistry, AgentSpec, init_agent

if TYPE_CHECKING:
    from geenii.agent.base_agent import BaseAgent
from geenii.ai import enumerate_providers
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
    for agent_dir in set(agent_paths()):
        _agents.load_from_directory(agent_dir)
    return _agents


def locate_agent_md_file(agent_name: str) -> str|None:
    for agent_dir in agent_paths():
        md_file_path = f"{agent_dir}/{agent_name}.md"
        if os.path.exists(md_file_path):
            return md_file_path
    return None

def init_agent_by_name(name: str, context_id: str | None = None) -> BaseAgent:
    """Load an agent configuration from a markdown file and create an Agent instance."""
    md_file_path = locate_agent_md_file(name)
    if md_file_path is None:
        if name == "default":
            return init_fallback_agent()
        raise ValueError(f"Agent '{name}' not found.")

    try:
        agent_conf = AgentSpec.from_md_file(md_file_path)
        return init_agent(agent_conf, context_id=context_id)
    except Exception as e:
        raise e

def init_fallback_agent(context_id: str | None = None) -> BaseAgent:
    try:
        agent_conf = AgentSpec(
            name="default",
            class_name="geenii.agents.RoutingAgent",
            model=DEFAULT_COMPLETION_MODEL or "ollama:qwen3:8b",
            system=DEFAULT_AGENT_SYSTEM_PROMPT,
        )
        return init_agent(agent_conf, context_id=context_id)
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

    data = dict({
        "app": {
            "version": APP_VERSION,
            "cwd": os.getcwd(),
            "user_home_dir": get_user_home_dir(),
            "geenii_dir": GEENII_DIR,
            "geenii_working_dir": GEENII_WORKING_DIR,
            "cache_dir": CACHE_DIR,
        },
        "providers": [provider.model_dump() for provider in ai_providers],
    })

    # add system report
    # if not in DEV_MODE, remove the env variables from the report for security reasons
    report = get_system_report()
    if not os.environ.get("DEV_MODE", "0") == "1":
        if "env" in report:
            report["env"] = {k: v for k, v in report["env"].items() if k in allowed_env_vars}
    data.update({"system": report})

    return data