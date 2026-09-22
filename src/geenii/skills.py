import logging
import os
import re
from functools import cached_property
from pathlib import Path

import pydantic

from geenii.config import GEENII_DIR, read_user_settings, GEENII_WORKING_DIR
from geenii.utils.os_util import get_user_home_dir
from geenii.utils.mdfile import read_frontmatter_file

logger = logging.getLogger(__name__)


class SkillSpec(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(ignored_types=(cached_property,))

    path: str
    name: str
    description: str
    metadata: dict | None = pydantic.Field(default_factory=dict)
    allowed_tools: list[str] | None = pydantic.Field(default_factory=list)
    triggers: list[str] = pydantic.Field(default_factory=list)

    @cached_property
    def instructions(self) -> str:
        if not self.path:
            return ""
        _, body = read_frontmatter_file(self.path + "/SKILL.md")
        return body or ""

    @staticmethod
    def from_path(skill_path: Path | str):
        if isinstance(skill_path, str):
            skill_path = Path(skill_path)
        md_path = skill_path / "SKILL.md"
        skill_header, skill_body = read_frontmatter_file(str(md_path))
        if not skill_header or not isinstance(skill_header, dict):
            raise ValueError(f"Malformed skill markdown file: missing or invalid header in '{str(md_path)}'")
        if "name" not in skill_header or "description" not in skill_header:
            raise ValueError(
                f"Malformed skill markdown file: missing required 'name' or 'description' fields in header of '{str(md_path)}'")
        raw_triggers = skill_header.get("triggers", "")
        if isinstance(raw_triggers, list):
            triggers = [t.strip().lower() for t in raw_triggers if t.strip()]
        else:
            triggers = [t.strip().lower() for t in re.split(r'[,\s]+', str(raw_triggers)) if t.strip()]

        return SkillSpec(
            path=str(md_path.parent),
            name=skill_header.get("name"),
            description=skill_header.get("description", ""),
            metadata=skill_header.get("metadata", {}),
            allowed_tools=[t for t in skill_header.get("allowed-tools", "").split(" ") if t],
            triggers=triggers,
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
        logger.info(f"Skill '{skill.path}' registered.")

    def load(self, skill_name: str) -> SkillSpec | None:
        try:
            skill = self.skills[skill_name] if skill_name in self.skills else None
            if skill:
                logger.info(f"Skill '{skill_name}' already loaded.")
                return skill

            skill_dir = locate_skill_path(skill_name)
            if not skill_dir:
                #raise KeyError(f"Skill '{skill_name}' not found.")
                logger.warning(f"Skill '{skill_name}' does not exist or is not a directory.")
                return None
            skill = SkillSpec.from_path(skill_dir)
            self.register(skill)
            return skill
        except Exception as e:
            logger.critical(f"Error while loading skill: {str(e)}", exc_info=False)
            raise e

    def match_triggers(self, prompt: str) -> list[str]:
        """Return skill names whose triggers match words in the prompt (case-insensitive, word-boundary)."""
        prompt_lower = prompt.lower()
        matched = []
        for name, skill in self.skills.items():
            for trigger in skill.triggers:
                if re.search(r'\b' + re.escape(trigger) + r'\b', prompt_lower):
                    matched.append(name)
                    break
        return matched

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

def skill_paths() -> list[str]:
    _skill_paths = [
        #os.path.join(GEENII_DIR, "skills"),
        os.path.join(GEENII_WORKING_DIR, ".geenii", "skills"),
        os.path.join(get_user_home_dir(), ".geenii", "skills"),
    ]
    _settings = read_user_settings()
    if "skill_dirs" in _settings:
        for skill_dir in _settings["skill_dirs"]:
            if os.path.isdir(skill_dir):
                _skill_paths.append(skill_dir)
            else:
                print(f"Warning: Skill directory '{skill_dir}' does not exist or is not a directory.")


    # remove duplicates
    _skill_paths = list(dict.fromkeys(_skill_paths))
    return _skill_paths


def locate_skill_path(skill_name: str) -> Path | None:
    """
    Locate the directory containing the skill markdown file for the given skill name.

    :param skill_name: The name of the skill to locate.
    :return:
    """
    for _path in skill_paths():
        logger.info(f"Searching for skill '{skill_name}' in path: {_path}")
        skill_md_path = Path(_path) / skill_name / "SKILL.md"
        if skill_md_path.is_file():
            logger.info(f"Found skill '{skill_name}' in path: {_path}")
            return Path(_path) / skill_name
    return None


def register_skill_scripts(skill: SkillSpec, tool_registry) -> list[str]:
    """Discover executable scripts in a skill's scripts/ directory and register them as tools.

    Each script becomes a tool named '{skill_name}__{script_stem}'.
    Returns the list of registered tool names.
    """
    from geenii.tool.script import ScriptTool

    scripts_dir = Path(skill.path) / "scripts"
    logger.info("Registering scripts in skill directory: %s", scripts_dir)
    if not scripts_dir.is_dir():
        return []

    skill_base = Path(skill.path).resolve()
    registered = []
    for script in sorted(scripts_dir.iterdir()):
        logger.info(f"Registering script '{script.stem}' in skill directory: {script}")
        if not script.is_file() or not os.access(str(script), os.X_OK):
            logger.warning("Script is not executable: %s", script)
            continue
        resolved = script.resolve()
        if not str(resolved).startswith(str(skill_base)):
            logger.warning("Skipping script outside skill directory: %s", script)
            continue
        tool_name = f"{skill.name}__{script.stem}"
        if tool_registry.has(tool_name):
            logger.info("Script tool %s already registered, skipping.", tool_name)
            continue
        tool = ScriptTool(
            name=tool_name,
            description=f"Script from skill '{skill.name}': {script.stem}",
            script_path=str(resolved),
            parameters={"type": "object", "properties": {"args": {"type": "string", "description": "The tool arguments"}}},
        )
        tool_registry.register(tool)
        registered.append(tool_name)
        logger.info("Registered script tool: %s", tool_name)
    return registered
