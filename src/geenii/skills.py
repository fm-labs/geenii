import logging
import os
from dataclasses import dataclass
from pathlib import Path
import yaml

from geenii.config import DATA_DIR
from geenii.utils.mdfile import read_frontmatter_file

logger = logging.getLogger(__name__)


@dataclass
class SkillSpec:
    path: str
    name: str
    description: str
    #instructions: str | None = None
    metadata: dict | None = None

    def __init__(self, name: str, path: str):
        instructions_md_path = Path(self.path) / "SKILL.md"
        if not instructions_md_path.is_file():
            raise KeyError(f"No instructions found at path '{instructions_md_path}'")

        # read meta data on init
        header, _ = read_frontmatter_file(str(instructions_md_path))

        self.path = path
        self.name = name
        self.description = header.get("description")
        self.metadata = header.get("metadata", {})
        self._instruction_md_path = instructions_md_path

    @property
    def instructions(self) -> str:
        # lazy load instructions
        _, body = read_frontmatter_file(str(self._instruction_md_path))
        return body


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
            skill = SkillSpec(skill_name, f"{DATA_DIR}/skills/{skill_name}")
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
                        skill = SkillSpec(str(item), str(Path(base_path / item)))
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

