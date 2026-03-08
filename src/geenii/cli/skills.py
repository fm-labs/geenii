import os
import shutil

import click.core

from geenii.cli.base import BaseCli
from geenii.config import DATA_DIR
from geenii.skills import SkillRegistry


class SkillsCli(BaseCli):

    @property
    def skills(self) -> SkillRegistry:
        if not self._skills:
            self._skills = SkillRegistry()
            self.info(f"Loading skills from directory '{DATA_DIR}/skills'...")
            self._skills.register_all_from_directory(f"{DATA_DIR}/skills")
        return self._skills

    def __init__(self, cli: click.core.Group):
        super().__init__(cli)
        self._skills = None

        @cli.group()
        def skills():
            """Manage skills."""
            pass

        @skills.command(name="list")
        def list_skills():
            """List all registered skills."""
            for skill in self.skills.skills:
                self.success(f"- {skill}: {self.skills.get(skill).description}")


        @skills.command(name="inspect")
        @click.argument("name")
        def inspect_skill(name: str):
            """
            Show details for a specific skill.
            """
            skill = self.skills.get(name)
            if skill:
                print(f"Path: {skill.path}")
                print(f"Name: {skill.name}")
                print(f"Description: {skill.description}")
                print(f"Metadata:")
                if skill.metadata:
                    for key, value in skill.metadata.items():
                        print(f"- {key}: {value}")
                print(f"Instructions:")
                print(f"---" * 13)
                print(skill.instructions)
                print(f"---" * 13)
            else:
                print(f"Skill '{name}' not found.")


        @skills.command(name="install")
        @click.argument("name")
        @click.argument("source")
        def install_skill(name: str, source: str):
            """
            Install a new skill from a given source (e.g., GitHub repo, local file).
            """
            target_dir = f"{DATA_DIR}/skills/{name}"

            # validate source
            if not source.startswith("file://"):
                self.error("Currently only local file sources are supported. Please provide a source in the format 'file://path/to/skill'.")
                return

            src_dir = source[len("file://"):]
            if not os.path.isdir(src_dir):
                self.error(f"Dir '{src_dir}' does not exist.")
                return

            # make sure target directory does not already exist
            if os.path.exists(target_dir):
                self.error(f"Skill '{name}' already exists. Please choose a different name or remove the existing skill first.")
                return

            shutil.copytree(src_dir, target_dir)
            self.success(f"Skill '{name}' installed successfully from '{source}'.")

