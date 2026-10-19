from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from geenii.agent.base import DEFAULT_AGENT_SYSTEM_PROMPT
from geenii.agent.env import AgentEnvStore
from geenii.agent.registry import AgentRegistry, AgentSpec, logger
from geenii.flows import FlowRegistry
from geenii.hitl import HumanInTheLoopController
from geenii.memory import ChatMemory
from geenii.tool.registry import ToolRegistry
from geenii.tools import init_builtin_tools, init_mcp_server_tools

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
    # cwd = BOT_WORKING_DIR
    return init_agent_by_name(name, cwd=None)


def makedirs_safe(path: str):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        print(f"Error creating directory {path}: {e}")

def make_app_directories():
    # ensure internal directories exist
    makedirs_safe(f"{CACHE_DIR}")
    makedirs_safe(f"{CACHE_DIR}/logs")


def agent_paths() -> list[tuple[str, str]]:
    return [
        (f"{GEENII_WORKING_DIR}/.geenii/agents", "project"),
        (f"{get_user_home_dir()}/.geenii/agents", "user"),
        ("/var/geenii/agents", "global"),
    ]


def init_global_agent_registry() -> AgentRegistry:
    _agents = AgentRegistry()
    # default
    _agents._agent_configs.update({"default": AgentSpec(
        name="default",
        model=DEFAULT_COMPLETION_MODEL or "ollama:qwen3:8b",
        scope="global"
    )})
    # routing
    _agents._agent_configs.update({"routing": AgentSpec(
        name="routing",
        class_name="geenii.agents.RoutingAgent",
        model=DEFAULT_COMPLETION_MODEL or "ollama:qwen3:8b",
        scope="global"
    )})
    # chatgpt
    _agents._agent_configs.update({"chatgpt": AgentSpec(
        name="chatgpt",
        model="openai:gpt-3.5-turbo",
        scope="global"
    )})
    # anthropic
    _agents._agent_configs.update({"claude": AgentSpec(
        name="claude",
        model="anthropic:claude-opus-4-6",
        scope="global"
    )})

    for (agent_dir, scope) in set(agent_paths()):
        _agents.load_from_directory(agent_dir, scope=scope)
    return _agents


def locate_agent_md_file(agent_name: str) -> tuple[str, str] | tuple[None, None]:
    for (agent_dir, scope) in agent_paths():
        md_file_path = f"{agent_dir}/{agent_name}.md"
        if os.path.exists(md_file_path):
            return md_file_path, scope
    return None, None

def init_agent_by_name(name: str, context_id: str | None = None, cwd: str | None = None) -> BaseAgent:
    """Load an agent configuration from a markdown file and create an Agent instance."""
    try:
        md_file_path, scope = locate_agent_md_file(name)
        if md_file_path is None:
            if name == "default":
                return init_default_agent(context_id=context_id)
            elif name == "auto":
                return init_routing_agent(context_id=context_id)
            else:
                raise ValueError(f"Agent '{name}' not found.")

        print(f"Loading agent '{name}' (Context {context_id})")
        agent_conf = AgentSpec.from_md_file(md_file_path)
        agent_conf.scope = scope

        if cwd is not None:
            agent_conf.working_dir = cwd
        return init_agent(agent_conf, context_id=context_id)
    except Exception as e:
        raise e


def init_agent(agent_conf: AgentSpec,
               context_id: str | None = None,
               *,
               memory: ChatMemory | None = None,
               hitl: HumanInTheLoopController | None = None) -> BaseAgent:
    """Create a new agent instance from its spec. `memory` and `hitl` override the agent's defaults."""
    # todo check model provider configuration
    # todo check model availability
    logger.info(f"Loading agent '{agent_conf.name}' with class '{agent_conf.class_name}'.")

    tool_registry = ToolRegistry()
    if agent_conf.tools is not None:
        for tool in agent_conf.tools:
            if tool in ('read', 'write', 'bash'):
                init_builtin_tools(tool_registry)
                break

    if agent_conf.mcp_servers is not None and len(agent_conf.mcp_servers) > 0:
        mcp_servers = agent_conf.mcp_servers
        init_mcp_server_tools(tool_registry, set(mcp_servers))

    skill_registry = SkillRegistry()
    if agent_conf.skills is not None:
        for skill in agent_conf.skills:
            logger.info(f"Adding skill '{skill}' to agent '{agent_conf.name}'.")
            skill_registry.load(skill)

    agent_class_name = "geenii.agents.Agent"
    if agent_conf.class_name is not None:
        agent_class_name = agent_conf.class_name

    cwd = agent_conf.working_dir

    env_store = AgentEnvStore()
    env = env_store.resolve(agent_conf.name)
    secret_keys = set(env_store.secret_keys(agent_conf.name))

    # instance from class path string
    try:
        module_path, class_name = agent_class_name.rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        agent_class = getattr(module, class_name)

        logger.info(f"Loading agent '{agent_conf.name}' with class '{agent_conf.class_name}' and Context '{context_id}'.")
        agent = agent_class(name=agent_conf.name, description=agent_conf.description,
                            model=agent_conf.model, system_prompt=agent_conf.full_instructions,
                            allowed_tools=set(agent_conf.tools), mcp_servers=agent_conf.mcp_servers,
                            tool_registry=tool_registry, skill_registry=skill_registry,
                            context_id=context_id, memory=memory, hitl=hitl, cwd=cwd,
                            env=env, secret_keys=secret_keys)
        return agent
    except Exception as e:
        logger.error(f"Error loading agent class '{agent_class_name}': {str(e)}", exc_info=e)
        raise ValueError(f"Error loading agent class '{agent_class_name}': {str(e)}")


def init_default_agent(context_id: str | None = None) -> BaseAgent:
    try:
        agent_conf = AgentSpec(
            name="default",
            class_name="geenii.agents.Agent",
            model=DEFAULT_COMPLETION_MODEL or "ollama:qwen3:8b",
            system=DEFAULT_AGENT_SYSTEM_PROMPT,
            scope="global"
        )
        return init_agent(agent_conf, context_id=context_id)
    except Exception as e:
        raise e

def init_routing_agent(context_id: str | None = None) -> BaseAgent:
    try:
        agent_conf = AgentSpec(
            name="routing",
            class_name="geenii.agents.RoutingAgent",
            model=DEFAULT_COMPLETION_MODEL or "ollama:qwen3:8b",
            system=DEFAULT_AGENT_SYSTEM_PROMPT,
            scope="global"
        )
        return init_agent(agent_conf, context_id=context_id)
    except Exception as e:
        raise e

def init_global_skill_registry() -> SkillRegistry:
    skill_reg = SkillRegistry()
    for skill_path in skill_paths():
        print("Loading skills from", skill_path)
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


def flow_dirs() -> list[str]:
    """Directories flows are loaded from: the user's, then the working directory's (without duplicates)"""
    dirs = [Path(get_user_home_dir(), ".geenii", "flows"), Path(GEENII_DIR, "flows")]
    return list(dict.fromkeys(str(d.resolve()) for d in dirs))


def init_flow_registry() -> FlowRegistry:
    reg = FlowRegistry()
    for d in flow_dirs():
        reg.load_all_from_dir(d)
    return reg
