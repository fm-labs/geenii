import os
import shutil

import click.core

from geenii.cli.click_helper import click_success, click_error
from geenii.config import USER_DIR
from geenii.g import init_skills


@click.group()
def skills():
    """Manage skills."""
    pass

@skills.command(name="list")
def list_skills():
    """List all registered skills."""
    _skills = init_skills()
    for skill in _skills.skills:
        click_success(f"- {skill}: {_skills.get(skill).description[:100]}...")


@skills.command(name="inspect")
@click.argument("name")
def inspect_skill(name: str):
    """
    Show details for a specific skill.
    """
    _skills = init_skills()
    skill = _skills.get(name)
    if skill:
        print(f"Path: {skill.dir_path}")
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
    target_dir = f"{USER_DIR}/skills/{name}"

    # validate source
    if not source.startswith("file://"):
        click_error("Currently only local file sources are supported. Please provide a source in the format 'file://path/to/skill'.")
        return

    src_dir = source[len("file://"):]
    if not os.path.isdir(src_dir):
        click_error(f"Dir '{src_dir}' does not exist.")
        return

    # make sure target directory does not already exist
    if os.path.exists(target_dir):
        click_error(f"Skill '{name}' already exists. Please choose a different name or remove the existing skill first.")
        return

    shutil.copytree(src_dir, target_dir)
    click_success(f"Skill '{name}' installed successfully from '{source}'.")

