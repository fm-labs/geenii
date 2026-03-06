from fastapi import APIRouter, Depends
from starlette.requests import Request

from geenii.skills import SkillRegistry

router = APIRouter(prefix="/skills", tags=["skills"])


def dep_skill_registry(request: Request):
    return request.app.state.skill_registry

@router.get("/")
def get_skills(registry: SkillRegistry = Depends(dep_skill_registry)):
    skills = registry.skills
    print(f"Found {len(skills)} skills in registry.")
    return skills

@router.post("/{skill_name}/prompt")
async def execute_skill(skill_name: str, args: dict, registry: SkillRegistry = Depends(dep_skill_registry)):
    skill = registry.get(skill_name)
    if not skill:
        raise ValueError(f"Skill '{skill_name}' not found.")
    return await skill.invoke(args=args)
