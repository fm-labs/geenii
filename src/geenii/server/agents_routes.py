import logging

from fastapi import APIRouter
from fastapi.params import Depends
from starlette.requests import Request

from geenii.agent.registry import AgentRegistry

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

