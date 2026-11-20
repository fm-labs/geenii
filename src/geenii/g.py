from __future__ import annotations

import os
from typing import TYPE_CHECKING

from geenii.agent.base import DEFAULT_AGENT_SYSTEM_PROMPT
from geenii.agent.env import AgentEnvStore
from geenii.agent.registry import AgentRegistry, AgentSpec, logger
from geenii.flows import FlowRegistry
from geenii.hitl import HumanInTheLoopController
from geenii.memory import ChatMemory
from geenii.plugins import plugin_agents, plugin_tools
from geenii.tool.registry import ToolRegistry
from geenii.tools import _redact_env_vars, init_builtin_os_tools, init_mcp_server_tools, init_builtin_webtools

if TYPE_CHECKING:
    from geenii.agent.base_agent import BaseAgent
from geenii.ai import enumerate_providers
from geenii.bots import BotInterface
from geenii.config import (
    APP_VERSION,
    DEFAULT_COMPLETION_MODEL,
    GEENII_CACHE_DIR,
    GEENII_USER_HOME,
    GEENII_WORKING_DIR,
    MCP_AGENT_WAIT_TIMEOUT,
    agent_paths,
    flow_dirs,
    project_paths,
    skill_paths,
)
from geenii.skills import SkillRegistry
from geenii.utils.os_util import get_user_home_dir
from geenii.utils.system_util import get_system_report


def get_bot(botname: str) -> BotInterface:
    # return EchoBot(botname=botname)
    # return SimpleBot(botname=botname)
    # return DemoAgent(botname=botname)

    if not botname.startswith("geenii:bot:"):
        raise ValueError(f"Invalid bot name: {botname}. Bot names must start with 'geenii:bot:'")

    name = botname[len("geenii:bot:") :]
    # cwd = BOT_WORKING_DIR
    return init_agent_by_name(name, cwd=None)


def init_global_agent_registry(registry: AgentRegistry | None = None, projects: bool = False) -> AgentRegistry:
    registry = registry or AgentRegistry()
    # default
    registry._specs.update(
        {
            "default": AgentSpec(
                name="default",
                model=DEFAULT_COMPLETION_MODEL,
                class_name="geenii.agents.RoutingAgent",
                scope="global",
            )
        }
    )
    # routing
    # registry._agent_configs.update(
    #     {
    #         "routing": AgentSpec(
    #             name="routing",
    #             class_name="geenii.agents.RoutingAgent",
    #             model=DEFAULT_COMPLETION_MODEL,
    #             scope="global",
    #         )
    #     }
    # )
    # chatgpt
    registry._specs.update({"chatgpt": AgentSpec(name="chatgpt", model="openai:gpt-4o-mini", scope="global")})
    # claude
    registry._specs.update({"claude": AgentSpec(name="claude", model="anthropic:claude-opus-4-6", scope="global")})
    # deepseek
    #registry._agent_configs.update({"deepseek": AgentSpec(name="deepseek", model="ollama:deepseek:v1", scope="global")})

    for agent_dir, scope in set(agent_paths()):
        registry.load_from_directory(agent_dir, scope=scope)

    # agents added by plugins; agent md files with the same name take precedence
    registry._specs.update(plugin_agents())

    # also load from all registered projects
    if projects:
        for project_dir in project_paths():
            logger.info(f"Loading project '{project_dir}'")
            registry.load_from_directory(os.path.join(project_dir, ".geenii", "agents"), scope="project")

    return registry


# The global agent registry, built on first use. Building it loads plugins, and plugins import modules that
# import geenii.g, so it must never be built while geenii.g itself is being imported.
_agent_registry: AgentRegistry | None = None


def get_agent_registry() -> AgentRegistry:
    """The global agent registry, built on the first call."""
    global _agent_registry
    if _agent_registry is None:
        _agent_registry = init_global_agent_registry()
    return _agent_registry


def reload_global_agent_registry() -> AgentRegistry:
    """Build the global agent registry again (e.g. after agent files changed)."""
    global _agent_registry
    _agent_registry = init_global_agent_registry()
    return _agent_registry

def locate_agent_md_file(agent_name: str) -> tuple[str, str] | tuple[None, None]:
    for agent_dir, scope in agent_paths():
        md_file_path = f"{agent_dir}/{agent_name}.md"
        if os.path.exists(md_file_path):
            return md_file_path, scope
    return None, None


def init_agent_by_name(name: str, context_id: str | None = None, cwd: str | None = None) -> BaseAgent:
    """Load an agent configuration from a markdown file and create an Agent instance."""
    try:
        md_file_path, scope = locate_agent_md_file(name)
        if md_file_path is None:
            plugin_spec = plugin_agents().get(name)
            if plugin_spec is not None:
                if cwd is not None:
                    plugin_spec.working_dir = cwd
                return init_agent(plugin_spec, context_id=context_id)
            if name == "default":
                return init_default_agent(context_id=context_id)
            #elif name == "auto":
            #    return init_routing_agent(context_id=context_id)
            else:
                raise ValueError(f"Agent '{name}' not found.")

        print(f"Loading agent '{name}' (Context {context_id})")
        agent_conf = AgentSpec.from_md_file(md_file_path)
        agent_conf.scope = scope

        if cwd is not None:
            agent_conf.working_dir = cwd
        return init_agent(agent_conf, context_id=context_id)
    except Exception:
        raise


def init_agent(
    agent_spec: AgentSpec,
    context_id: str | None = None,
    model: str | None = None,
    *,
    memory: ChatMemory | None = None,
    hitl: HumanInTheLoopController | None = None,
) -> BaseAgent:
    """Create a new agent instance from its spec. `memory` and `hitl` override the agent's defaults."""
    # todo check model provider configuration
    # todo check model availability
    logger.info(f"Loading agent '{agent_spec.name}' with class '{agent_spec.class_name}'.")

    tool_registry = ToolRegistry()
    if agent_spec.tools is not None:
        wanted = set(agent_spec.tools)
        if wanted & {"read", "write", "bash"}:
            init_builtin_os_tools(tool_registry)
        if "web_fetch" in wanted:
            init_builtin_webtools(tool_registry)

        # tools added by plugins
        _plugin_tools = plugin_tools()
        for tool in agent_spec.tools:
            if _plugin_tools.has(tool) and not tool_registry.has(tool):
                tool_registry.register(_plugin_tools.get(tool))

    if agent_spec.mcp_servers is not None and len(agent_spec.mcp_servers) > 0:
        # waits for servers that are still loading in the background, up to the timeout
        init_mcp_server_tools(tool_registry, set(agent_spec.mcp_servers), timeout=MCP_AGENT_WAIT_TIMEOUT)

    skill_registry = SkillRegistry()
    if agent_spec.skills is not None:
        for skill in agent_spec.skills:
            logger.info(f"Adding skill '{skill}' to agent '{agent_spec.name}'.")
            skill_registry.load(skill)

    agent_class_name = "geenii.agents.Agent"
    if agent_spec.class_name is not None:
        agent_class_name = agent_spec.class_name

    cwd = agent_spec.working_dir

    env_store = AgentEnvStore()
    env = env_store.resolve(agent_spec.name)
    secret_keys = set(env_store.secret_keys(agent_spec.name))

    # instance from class path string
    try:
        module_path, class_name = agent_class_name.rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        agent_class = getattr(module, class_name)

        logger.info(
            f"Loading agent '{agent_spec.name}' with class '{agent_spec.class_name}' and Context '{context_id}'."
        )
        agent = agent_class(
            name=agent_spec.name,
            description=agent_spec.description,
            model=model or agent_spec.model,
            system_prompt=agent_spec.full_instructions,
            allowed_tools=set(agent_spec.tools),
            mcp_servers=agent_spec.mcp_servers,
            tool_registry=tool_registry,
            skill_registry=skill_registry,
            context_id=context_id,
            memory=memory,
            hitl=hitl,
            cwd=cwd,
            env=env,
            secret_keys=secret_keys,
        )
        return agent
    except Exception as e:
        logger.error(f"Error loading agent class '{agent_class_name}': {e!s}", exc_info=e)
        raise ValueError(f"Error loading agent class '{agent_class_name}': {e!s}")


def init_default_agent(context_id: str | None = None) -> BaseAgent:
    try:
        agent_conf = AgentSpec(
            name="default",
            #class_name="geenii.agents.Agent",
            class_name="geenii.agents.RoutingAgent",
            model=DEFAULT_COMPLETION_MODEL,
            system=DEFAULT_AGENT_SYSTEM_PROMPT,
            scope="global",
        )
        return init_agent(agent_conf, context_id=context_id)
    except Exception:
        raise


# def init_routing_agent(context_id: str | None = None) -> BaseAgent:
#     try:
#         agent_conf = AgentSpec(
#             name="routing",
#             class_name="geenii.agents.RoutingAgent",
#             model=DEFAULT_COMPLETION_MODEL,
#             system=DEFAULT_AGENT_SYSTEM_PROMPT,
#             scope="global",
#         )
#         return init_agent(agent_conf, context_id=context_id)
#     except Exception:
#         raise


def init_global_skill_registry() -> SkillRegistry:
    skill_reg = SkillRegistry()
    for skill_path in skill_paths():
        print("Loading skills from", skill_path)
        skill_reg.register_all_from_directory(skill_path)
    return skill_reg


def get_app_info() -> dict:
    allowed_env_vars = ["PATH", "HOME", "USER", "USERNAME"]

    ai_providers = enumerate_providers()

    data = {
        "app": {
            "version": APP_VERSION,
            "cwd": os.getcwd(),
            "user_home_dir": get_user_home_dir(),
            "geenii_user_home_dir": GEENII_USER_HOME,
            "geenii_working_dir": GEENII_WORKING_DIR,
            "cache_dir": GEENII_CACHE_DIR,
        },
        "providers": [provider.model_dump() for provider in ai_providers],
    }

    # add system report
    # if not in DEV_MODE, remove the env variables from the report for security reasons
    report = get_system_report()
    if "env" in report:
        report["env"] = _redact_env_vars(report["env"])
        if os.environ.get("DEV_MODE", "0") != "1":
            report["env"] = {k: v for k, v in report["env"].items() if k in allowed_env_vars}
    data.update({"system": report})

    return data


def init_flow_registry() -> FlowRegistry:
    reg = FlowRegistry()
    for d in flow_dirs():
        reg.load_all_from_dir(d)
    return reg
