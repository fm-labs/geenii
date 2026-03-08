import os
import logging

import pydantic

from geenii.agent.base import DEFAULT_AGENT_SYSTEM_PROMPT
from geenii.agents import BaseAgent
from geenii.chat.chat_bots import BotInterface
from geenii.config import DATA_DIR
from geenii.skills import SkillRegistry
from geenii.tool.registry import ToolRegistry
from geenii.utils.json_util import read_json

logger = logging.getLogger(__name__)

class AgentConfig(pydantic.BaseModel):
    """
    BotConfig represents the configuration for a agent, including its name, model, system prompt, description, tools, and skills.
    This can be used to define agents in JSON files and load them into Agent instances.
    """
    name: str
    model: str
    system: str
    label: str | None = None
    description: str | None = None
    tools: list[str] | None = pydantic.Field(default_factory=list)
    mcp_servers: dict[str, dict] | None = pydantic.Field(default_factory=dict)
    skills: list[str] | None = pydantic.Field(default_factory=list)
    model_parameters: dict | None = pydantic.Field(default_factory=dict)

    @property
    def path(self):
        """The path to the agent's directory, which can contain additional files like INSTRUCTIONS.md"""
        return f"{DATA_DIR}/agents/{self.name}"


    @property
    def instructions(self) -> str:
        """
        The contents of INSTRUCTIONS.md in the agent's directory, if it exists.
        This can be used to provide additional instructions for the agent that are appended to the system prompt.
        """
        instructions_path = f"{self.path}/INSTRUCTIONS.md"
        if os.path.exists(instructions_path):
            with open(instructions_path, "r") as f:
                return f.read()
        return ""

    @property
    def full_instructions(self) -> str:
        """
        Build the full system prompt for the agent by combining the base system prompt with any additional instructions from INSTRUCTIONS.md.
        """
        system_prompt = self.system or DEFAULT_AGENT_SYSTEM_PROMPT
        instructions_path = f"{self.path}/INSTRUCTIONS.md"
        if os.path.exists(instructions_path):
            with open(instructions_path, "r") as f:
                instructions = f.read()
                system_prompt += f"\n\n{instructions}"
        return system_prompt


def init_agent(agent_conf: AgentConfig) -> BaseAgent:
    tool_registry = ToolRegistry()
    # init_builtin_tools(tool_registry)
    # init_mcp_server_tools_sync(tool_registry)
    # for tool in tools:
    #    tool_registry.allow_tool(tool)
    # for mcp_server_id, mcp_server_config in mcp_servers.items():
    #    tool_registry.register_mcp_server(mcp_server_id, mcp_server_config)
    skill_registry = SkillRegistry()
    for skill in agent_conf.skills:
        skill_registry.load(skill)

    #system_prompt = agent_conf.system or DEFAULT_AGENT_SYSTEM_PROMPT
    ## if an INSTRUCTIONS.md exist in agent's directory, we can append it to the system prompt
    #agent_dir = f"{DATA_DIR}/agents/{agent_conf.name}"
    #instructions_path = f"{agent_dir}/INSTRUCTIONS.md"
    #if os.path.exists(instructions_path):
    #    with open(instructions_path, "r") as f:
    #        instructions = f.read()
    #        system_prompt += f"\n\n{instructions}"

    agent_class_name = "geenii.agents.Agent"
    if agent_conf.name == "default":
        agent_class_name = "geenii.agents.RoutingAgent"

    # instance from class  path string
    agent = None
    try:
        module_path, class_name = agent_class_name.rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        agent_class = getattr(module, class_name)
    except Exception as e:
        logger.error(f"Error loading agent class '{agent_class_name}': {str(e)}", exc_info=e)
        raise ValueError(f"Error loading agent class '{agent_class_name}': {str(e)}")

    agent = agent_class(name=agent_conf.name, description=agent_conf.description,
                        model=agent_conf.model, system_prompt=agent_conf.full_instructions,
                        allowed_tools=set(agent_conf.tools),
                        tool_registry=tool_registry, skill_registry=skill_registry)
    return agent


class AgentRegistry:
    def __init__(self):
        self._agent_configs: dict[str, AgentConfig] = {}
        self._agents: dict[str, BaseAgent] = {}

    def get_config(self, name) -> AgentConfig | None:
        """Get the configuration for a agent by name. Returns None if no configuration is found."""
        return self._agent_configs.get(name)

    def get_instance(self, name) -> BotInterface | None:
        """Get a Agent instance by name. If the agent is not already loaded, it will be initialized from its configuration if available. Returns None if no agent instance can be found or initialized."""
        if name in self._agents:
            return self._agents[name]
        elif name in self._agent_configs:
            try:
                agent = init_agent(self._agent_configs[name])
                self._register_agent(agent)
                return agent
            except Exception as e:
                logger.error(f"Error initializing agent '{name}': {str(e)}", exc_info=e)
                return None
        return self._agents.get(name)

    def list_configured(self) -> set[str]:
        """Names of configured agents"""
        return set(self._agent_configs.keys())

    def list_loaded(self) -> set[str]:
        """Names of currently loaded agents"""
        return set(self._agents.keys())

    def unload_agent(self, name: str) -> None:
        """Unload a agent by name. This removes the agent instance from the registry but keeps its configuration available for future loading. If the agent is not currently loaded, this method does nothing."""
        if name in self._agents:
            del self._agents[name]
            logger.info(f"Agent '{name}' unloaded.")
        else:
            logger.warning(f"Attempted to unload agent '{name}' which is not currently loaded.")

    def _register_agent(self, agent: BaseAgent) -> None:
        """Internal method"""
        if not agent or not isinstance(agent, BaseAgent):
            raise ValueError("Invalid agent object provided for registration.")
        if agent.name in self._agents:
            raise ValueError(f"Agent with name '{agent.name}' is already registered.")
        self._agents[agent.name] = agent
        logger.info(f"Agent '{agent.name}' registered.")

    def from_config_file(self, config_path: str):
        if os.path.exists(config_path):
            data = read_json(config_path)
            if not isinstance(data, list):
                raise ValueError(
                    f"Invalid agent configuration in {config_path}: expected a JSON list of BotConfig data.")
            for config in data:
                try:
                    agent_conf = AgentConfig.model_validate(config)
                    self._agent_configs[agent_conf.name] = agent_conf
                    logger.info(f"Agent '{agent_conf.name}' registered.")
                except Exception as e:
                    logger.error(f"Error loading agent from config: {str(e)}", exc_info=e)
        else:
            logger.warning(f"Agent configuration file not found at {config_path}. No agents loaded.")
