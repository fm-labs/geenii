import logging

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from starlette.requests import Request

from geenii.agent.registry import AgentRegistry
from geenii.agents import Agent
from geenii.datamodels import AgentCommand, Problem
from geenii.skills import SkillRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


def dep_agent_registry(request: Request) -> AgentRegistry:
    return request.app.state.agent_registry

@router.get("/")
def list_agents(agent_registry: AgentRegistry = Depends(dep_agent_registry)):
    """
    List all configured agents.
    """
    agents = agent_registry.configs.values()
    agents_list = []
    for agent in agents:
        agents_list.append(agent)
    return agents_list


@router.get("/{name}", responses={404: {"model": Problem, "description": "Agent not found"}})
def get_agent(name: str, agent_registry: AgentRegistry = Depends(dep_agent_registry)) -> dict:
    """
    The agent's spec plus its `instructions` (the markdown body of the spec file).
    """
    spec = agent_registry.get_config(name)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found.")
    try:
        instructions = spec.instructions
    except Exception as e:
        logger.warning(f"Could not read instructions of agent '{name}': {e}")
        instructions = ""
    return {**spec.model_dump(), "instructions": instructions}


@router.get("/{name}/commands", responses={404: {"model": Problem, "description": "Agent not found"}})
def list_agent_commands(name: str, agent_registry: AgentRegistry = Depends(dep_agent_registry)) -> list[AgentCommand]:
    """
    Slash commands the agent understands: the built-in commands, then one per configured skill
    ("/<skill>" activates the skill). Commands are listed without the leading slash.
    """
    spec = agent_registry.get_config(name)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found.")

    commands = [AgentCommand(command=c, description=d) for c, d in Agent.BUILTIN_COMMANDS.items()]
    skills = SkillRegistry()
    for skill_name in sorted(spec.skills or []):
        # the macro handler matches lowercased names, and built-in commands win over skills
        if skill_name.lower() in Agent.BUILTIN_COMMANDS:
            logger.warning(f"Skill '{skill_name}' of agent '{name}' is shadowed by the built-in command '/{skill_name.lower()}'.")
            continue
        try:
            skill = skills.load(skill_name)
        except Exception as e:
            logger.warning(f"Skipping skill '{skill_name}' of agent '{name}': {e}")
            continue
        if skill is None:
            continue
        commands.append(AgentCommand(command=skill.name, description=skill.description))
    return commands
