import logging
import os
from pathlib import Path

import pydantic

from geenii.config import DATA_DIR
from geenii.utils.mdfile import read_frontmatter_file

logger = logging.getLogger(__name__)


class SkillSpec(pydantic.BaseModel):
    dir_path: str
    name: str
    description: str
    #instructions: str | None = None
    metadata: dict | None = pydantic.Field(default_factory=dict)

    @property
    def instructions(self) -> str:
        """
        The contents of the body of the skill markdown file, which can contain additional instructions or information about the skill.
        """
        if not self.dir_path:
            return ""
        _, body = read_frontmatter_file(self.dir_path)
        return body

    @staticmethod
    def from_path(skill_path: str):
        md_path = os.path.join(skill_path, "SKILL.md")
        skill_header, skill_body = read_frontmatter_file(md_path)
        if not skill_header or not isinstance(skill_header, dict):
            raise ValueError(f"Malformed skill markdown file: missing or invalid header in '{md_path}'")
        if not "name" in skill_header or "description" not in skill_header:
            raise ValueError(f"Malformed skill markdown file: missing required 'name' or 'description' fields in header of '{md_path}'")
        return SkillSpec(
            dir_path=str(Path(md_path).parent),
            name=skill_header.get("name"),
            description=skill_header.get("description", ""),
            metadata=skill_header
        )


class SkillRegistry:
    """
    Registry for managing skills. Provides methods to register, retrieve, and load skills from the filesystem.
    """

    def __init__(self):
        self.skills = {}

    def get(self, skill_name) -> SkillSpec | None:
        return self.skills.get(skill_name)

    def names(self) -> set[str]:
        return set(self.skills.keys())
    
    def register(self, skill: SkillSpec):
        if not skill or not isinstance(skill, SkillSpec):
            raise ValueError("Invalid skill object provided for registration.")
        if skill.name in self.skills:
            raise ValueError(f"Skill with name '{skill.name}' is already registered.")
        self.skills[skill.name] = skill
        logger.info(f"Skill '{skill.name}' registered.")

    def load(self, skill_name: str) -> SkillSpec | None:
        try:
            skill_dir = f"{DATA_DIR}/skills/{skill_name}"
            skill = SkillSpec.from_path(skill_dir)
            self.register(skill)
            return skill
        except Exception as e:
            logger.critical(f"Error while loading skill: {str(e)}", exc_info=e)

    def unload(self, skill_name: str) -> None:
        if skill_name in self.skills:
            del self.skills[skill_name]
            logger.info(f"Skill '{skill_name}' unloaded.")

    def register_all_from_directory(self, directory: str) -> None:
        base_path = Path(directory)
        if not base_path.is_dir():
            logger.warning(f"Skill directory '{directory}' does not exist or is not a directory.")
            return

        for item in base_path.iterdir():
            if item.is_dir():
                skill_md_path = Path(base_path / item / "SKILL.md")
                if skill_md_path.is_file():
                    try:
                        skill = SkillSpec.from_path(str(skill_md_path.parent))
                        self.register(skill)
                    except Exception as e:
                        logger.critical(f"Error while loading skill from '{item}': {str(e)}", exc_info=False)


# def build_skill_spec(skill_path: Path | str) -> SkillSpec:
#     """
#     Load a skill by name, optionally specifying the path to the skill directory.
#
#     :param skill_name: The name of the skill to load.
#     :param skill_path:  Optional path to the skill directory. If not provided, the function will attempt to locate it.
#     :return: A Skill object containing the loaded skill information.
#     """
#     skill_path = Path(skill_path).resolve()
#     if not skill_path or not skill_path.is_dir():
#         raise ValueError(f"Skill not found in path '{skill_path}'")
#
#     skill_header, skill_body = read_frontmatter_file(str(skill_path / "SKILL.md"))
#     skill = SkillSpec(name=skill_path.name,
#                       path=str(skill_path),
#                       description=skill_header.get("description"),
#                       metadata=skill_header)
#     return skill


# def skill_locate_path(skill_name: str) -> Path | None:
#     """
#     Locate the directory containing the skill markdown file for the given skill name.
#
#     :param skill_name: The name of the skill to locate.
#     :return:
#     """
#     base_paths = [
#         #os.path.join(os.getcwd(), skill_name),
#         os.path.join(DATA_DIR, "skills", skill_name)
#     ]
#     for path in base_paths:
#         logger.debug(f"Searching for skill '{skill_name}' in path: {path}")
#         _path = Path(path).absolute()
#         if _path.is_dir():
#             skill_md_path = _path / "SKILL.md"
#             if skill_md_path.is_file():
#                 logger.info(f"Found skill '{skill_name}' in path: {_path}")
#                 return _path
#     return None

