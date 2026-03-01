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
            self._skills.load_all_from_directory(f"{DATA_DIR}/skills")
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
                self.success(f"- {skill}: {self.skills.get_skill(skill).description}")

        @skills.command(name="inspect")
        @click.argument("name")
        def inspect_skill(name: str):
            """
            Show details for a specific skill.
            """
            skill = self.skills.get_skill(name)
            if skill:
                print(f"Name: {skill.name}")
                print(f"Description: {skill.description}")
                print(f"Instructions:\n{skill.instructions}")
            else:
                print(f"Skill '{name}' not found.")