import logging
import os
from pathlib import Path

import pydantic

from geenii.agent.base_agent import BaseAgent
from geenii.bots import BotInterface
from geenii.skills import SkillRegistry
from geenii.tool.registry import ToolRegistry
from geenii.utils.mdfile import read_frontmatter_file

logger = logging.getLogger(__name__)


class AgentSpec(pydantic.BaseModel):
    """
    Represents the configuration for an agent, including its name, model, system prompt, description, tools, and skills.
    """
    file_path: str | None = None # path to the spec file, used for loading additional instructions
    name: str
    model: str
    system: str | None = None
    label: str | None = None
    description: str | None = None
    tools: list[str] | None = pydantic.Field(default_factory=list)
    skills: list[str] | None = pydantic.Field(default_factory=list)
    model_parameters: dict | None = pydantic.Field(default_factory=dict)
    mcp_servers: list[str] | None = pydantic.Field(default_factory=list)
    class_name: str | None = None

    # @property
    # def working_dir(self):
    #     """The path to the agent's directory"""
    #     return f"{USER_DIR}/agents/{self.name}/"

    @property
    def instructions(self) -> str:
        """
        The contents of INSTRUCTIONS.md in the agent's directory, if it exists.
        """
        if not self.file_path:
            return ""
        _, body = read_frontmatter_file(self.file_path)
        return body

    @property
    def full_instructions(self) -> str:
        """
        Build the full system prompt for the agent by combining the base system prompt with any additional instructions from INSTRUCTIONS.md.
        """
        full = self.system or ""
        if self.instructions:
            full += "\n\n" + self.instructions
        return full.strip()

    @staticmethod
    def from_md_file(md_path: str):
        """
        Load agent configuration from a markdown file with frontmatter. The frontmatter should contain the fields defined in this model.
        """
        header, _ = read_frontmatter_file(md_path)
        if not isinstance(header, dict):
            raise ValueError(f"Invalid agent configuration in {md_path}: expected frontmatter to be a dictionary.")
        header["file_path"] = md_path
        return AgentSpec.model_validate(header)


def init_agent(agent_conf: AgentSpec) -> BaseAgent:
    # todo check model provider configuration
    # todo check model availability

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

    agent_class_name = "geenii.agents.Agent"
    if agent_conf.class_name is not None:
        agent_class_name = agent_conf.class_name

    # instance from class path string
    try:
        module_path, class_name = agent_class_name.rsplit(".", 1)
        module = __import__(module_path, fromlist=[class_name])
        agent_class = getattr(module, class_name)

        agent = agent_class(name=agent_conf.name, description=agent_conf.description,
                            model=agent_conf.model, system_prompt=agent_conf.full_instructions,
                            allowed_tools=set(agent_conf.tools), mcp_servers=agent_conf.mcp_servers,
                            tool_registry=tool_registry, skill_registry=skill_registry)
        return agent
    except Exception as e:
        logger.error(f"Error loading agent class '{agent_class_name}': {str(e)}", exc_info=e)
        raise ValueError(f"Error loading agent class '{agent_class_name}': {str(e)}")


class AgentRegistry:
    def __init__(self):
        self._agent_configs: dict[str, AgentSpec] = {}
        self._agents: dict[str, BaseAgent] = {}

    def get_config(self, name) -> AgentSpec | None:
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

    def load_from_file(self, config_path: str):
        if os.path.exists(config_path):
            try:
                agent_conf = AgentSpec.from_md_file(config_path)
                self._agent_configs[agent_conf.name] = agent_conf
                logger.debug(f"Agent config '{agent_conf.name}' loaded from file '{config_path}'.")
            except Exception as e:
                logger.error(f"Error loading agent from config file '{config_path}': {str(e)}", exc_info=e)
        else:
            logger.warning(f"Agent configuration file not found at {config_path}. No agents loaded.")

    def load_from_directory(self, directory: str) -> None:
        base_path = Path(directory)
        if not base_path.is_dir():
            logger.warning(f"Agent directory '{directory}' does not exist or is not a directory.")
            return
        for item in base_path.iterdir():
            if item.is_file() and item.name.endswith(".md"):
                file_path = Path(base_path / item.name)
                #logger.debug(f"Agent MD found at '{file_path}'")
                try:
                    agent_conf = AgentSpec.from_md_file(str(file_path))
                    self._agent_configs[agent_conf.name] = agent_conf
                    logger.debug(f"Agent config '{agent_conf.name}' loaded from file '{file_path}'.")
                except Exception as e:
                    logger.error(f"Error loading agent from config: {str(e)}", exc_info=e)
