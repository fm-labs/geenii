import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from starlette.requests import Request

from geenii.agent.registry import AgentRegistry
from geenii.datamodels import Problem
from geenii.skills import SkillRegistry, SkillSpec

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/skills", tags=["skills"])


def dep_skill_registry(request: Request) -> SkillRegistry:
    return request.app.state.skill_registry


def dep_agent_registry(request: Request) -> AgentRegistry:
    return request.app.state.agent_registry


def _list_scripts(skill: SkillSpec) -> list[str]:
    scripts_dir = Path(skill.path) / "scripts"
    if not scripts_dir.is_dir():
        return []
    return sorted(p.name for p in scripts_dir.iterdir() if p.is_file())


def _skill_summary(skill: SkillSpec, agent_registry: AgentRegistry) -> dict:
    used_by = sorted(a.name for a in agent_registry.configs.values() if skill.name in (a.skills or []))
    return {
        **skill.model_dump(exclude={"tool_filters"}),
        "source": str(Path(skill.path).parent),
        "scripts": _list_scripts(skill),
        "used_by": used_by,
    }


@router.get("/")
def list_skills(skill_registry: SkillRegistry = Depends(dep_skill_registry),
                agent_registry: AgentRegistry = Depends(dep_agent_registry)) -> list[dict]:
    """
    List the skills in the app's skill registry, sorted by name.
    """
    return [_skill_summary(skill_registry.get(name), agent_registry) for name in sorted(skill_registry.names())]


@router.get("/{name}", responses={404: {"model": Problem, "description": "Skill not found"}})
def get_skill(name: str,
              skill_registry: SkillRegistry = Depends(dep_skill_registry),
              agent_registry: AgentRegistry = Depends(dep_agent_registry)) -> dict:
    """
    The skill summary plus its `instructions` (the markdown body of SKILL.md).
    """
    skill = skill_registry.get(name)
    if skill is None:
        raise HTTPException(status_code=404, detail=f"Skill '{name}' not found.")
    try:
        instructions = skill.instructions
    except Exception as e:
        logger.warning(f"Could not read instructions of skill '{name}': {e}")
        instructions = ""
    return {**_skill_summary(skill, agent_registry), "instructions": instructions}
