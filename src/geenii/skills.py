import logging
import os
from dataclasses import dataclass
from pathlib import Path
import yaml

from geenii.config import DATA_DIR

logger = logging.getLogger(__name__)


@dataclass
class SkillSpec:
    path: str
    name: str
    description: str
    #instructions: str | None = None
    metadata: dict | None = None

    @property
    def instructions(self) -> str:
        instructions_md_path = Path(self.path) / "SKILL.md"
        if not instructions_md_path.is_file():
            return f"No instructions found at path '{instructions_md_path}'"

        _, skill_body = skill_md_read(str(instructions_md_path))
        return skill_body

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
            skill = build_skill_spec(f"{DATA_DIR}/skills/{skill_name}")
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
                        skill = build_skill_spec(Path(base_path / item))
                        self.register(skill)
                    except Exception as e:
                        logger.critical(f"Error while loading skill from '{item}': {str(e)}", exc_info=False)


def build_skill_spec(skill_path: Path | str) -> SkillSpec:
    """
    Load a skill by name, optionally specifying the path to the skill directory.

    :param skill_name: The name of the skill to load.
    :param skill_path:  Optional path to the skill directory. If not provided, the function will attempt to locate it.
    :return: A Skill object containing the loaded skill information.
    """
    skill_path = Path(skill_path).resolve()
    if not skill_path or not skill_path.is_dir():
        raise ValueError(f"Skill not found in path '{skill_path}'")

    skill_header, skill_body = skill_md_read(str(skill_path / "SKILL.md"))
    skill = SkillSpec(name=skill_path.name,
                      path=str(skill_path),
                      description=skill_header.get("description"),
                      metadata=skill_header)
    return skill


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


def skill_md_read(skill_file: str) -> tuple[dict, str]:
    """
    Read and parse the skill markdown file from the specified directory.

    :param skill_file: The directory containing the SKILL.md file.
    :return: A tuple containing the skill header and body content.
    """
    if not skill_file or not os.path.isfile(skill_file):
        raise ValueError(f"Skill markdown file not found: '{skill_file}'")

    contents = ""
    with open(skill_file, "r") as f:
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

    # the header str is expected to be in YAML format, we can parse it into a dict
    try:
        header_dict = yaml.safe_load(header)
    except yaml.YAMLError as e:
        raise ValueError(f"Malformed skill markdown file: error parsing header YAML. {str(e)}")

    return header_dict, body