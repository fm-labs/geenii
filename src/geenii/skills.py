import logging
import os
from dataclasses import dataclass
from pathlib import Path

from geenii.config import DATA_DIR

logger = logging.getLogger(__name__)

@dataclass
class Skill:
    name: str
    description: str
    instructions: str | None = None


class SkillRegistry:
    def __init__(self):
        self.skills = {}

    def get_skill(self, skill_name) -> Skill | None:
        return self.skills.get(skill_name)

    def list_skills(self) -> list[str]:
        return list(self.skills.keys())
    
    def register_skill(self, skill: Skill):
        if not skill or not isinstance(skill, Skill):
            raise ValueError("Invalid skill object provided for registration.")
        if skill.name in self.skills:
            raise ValueError(f"Skill with name '{skill.name}' is already registered.")
        self.skills[skill.name] = skill
        logger.info(f"Skill '{skill.name}' registered.")

    def load_skill(self, skill_name: str) -> Skill | None:
        try:
            skill = skill_load(skill_name)
            self.register_skill(skill)
            return skill
        except Exception as e:
            logger.critical(f"Error while loading skill: {str(e)}", exc_info=e)

    def unload_skill(self, skill_name: str) -> None:
        if skill_name in self.skills:
            del self.skills[skill_name]
            logger.info(f"Skill '{skill_name}' unloaded.")


def skill_load(skill_name: str) -> Skill:
    skill_path = skill_locate_path(skill_name)
    if not skill_path:
        raise ValueError(f"Skill '{skill_name}' not found in expected locations.")

    skill_header, skill_body = skill_read(str(skill_path))
    skill = Skill(name=skill_name, description=skill_name, instructions=skill_body)
    return skill


def skill_locate_path(skill_name: str) -> Path | None:
    base_paths = [
        #os.path.join(os.getcwd(), skill_name),
        os.path.join(DATA_DIR, "skills", skill_name)
    ]
    for path in base_paths:
        print(f"Checking for skill '{skill_name}' in path: {path}")
        _path = Path(path).absolute()
        if _path.is_dir():
            #skill_md_path = _path / "SKILL.md"
            #if skill_md_path.is_file():
            #    return _path
            return _path
    return None

def skill_read(skill_dir: str) -> tuple[str, str]:
    skill_md_path = f"{skill_dir}/SKILL.md"
    if not os.path.isfile(skill_md_path):
        raise ValueError(f"Skill markdown file not found in skill dir '{skill_dir}'")

    contents = ""
    with open(skill_md_path, "r") as f:
        contents = f.read()

    if not contents.startswith("---"):
        raise ValueError("Malformed skill markdown file: missing header delimiter.")

    # find the second occurrence of '---' to determine the end of the header
    second_header_index = contents.find("---", 3)
    if second_header_index == -1:
        raise ValueError("Malformed skill markdown file: missing second header delimiter.")

    # extract the header and body sections
    header = contents[3:second_header_index].strip()
    body = contents[second_header_index + 3:].strip()
    return header, body