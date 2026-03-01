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
    """
    Registry for managing skills. Provides methods to register, retrieve, and load skills from the filesystem.
    """

    def __init__(self):
        self.skills = {}

    def get_skill(self, skill_name) -> Skill | None:
        return self.skills.get(skill_name)

    def list_skill_names(self) -> set[str]:
        return set(self.skills.keys())
    
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

    def load_all_from_directory(self, directory: str) -> None:
        base_path = Path(directory)
        if not base_path.is_dir():
            logger.warning(f"Skill directory '{directory}' does not exist or is not a directory.")
            return

        for item in base_path.iterdir():
            if item.is_dir():
                try:
                    skill = skill_load(item.name, Path(base_path / item))
                    self.register_skill(skill)
                except Exception as e:
                    logger.critical(f"Error while loading skill from '{item}': {str(e)}", exc_info=False)


def skill_load(skill_name: str, skill_path: Path | None = None) -> Skill:
    """
    Load a skill by name, optionally specifying the path to the skill directory.

    :param skill_name: The name of the skill to load.
    :param skill_path:  Optional path to the skill directory. If not provided, the function will attempt to locate it.
    :return: A Skill object containing the loaded skill information.
    """
    if skill_path is None:
        skill_path = skill_locate_path(skill_name)
    if not skill_path:
        raise ValueError(f"Skill '{skill_name}' not found in expected locations.")

    skill_header, skill_body = skill_read(str(skill_path))
    skill = Skill(name=skill_name, description=skill_name, instructions=skill_body)
    return skill


def skill_locate_path(skill_name: str) -> Path | None:
    """
    Locate the directory containing the skill markdown file for the given skill name.

    :param skill_name: The name of the skill to locate.
    :return:
    """
    base_paths = [
        #os.path.join(os.getcwd(), skill_name),
        os.path.join(DATA_DIR, "skills", skill_name)
    ]
    for path in base_paths:
        logger.debug(f"Searching for skill '{skill_name}' in path: {path}")
        _path = Path(path).absolute()
        if _path.is_dir():
            skill_md_path = _path / "SKILL.md"
            if skill_md_path.is_file():
                logger.info(f"Found skill '{skill_name}' in path: {_path}")
                return _path
    return None


def skill_read(skill_dir: str) -> tuple[str, str]:
    """
    Read and parse the skill markdown file from the specified directory.

    :param skill_dir: The directory containing the SKILL.md file.
    :return: A tuple containing the skill header and body content.
    """
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