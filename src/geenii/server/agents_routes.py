import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Literal

import pydantic
import yaml
from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from starlette.requests import Request

from geenii.agent.env import AgentEnvStore, validate_env_key
from geenii.agent.registry import AgentRegistry, AgentSpec
from geenii.agents import Agent
from geenii.config import agent_paths
from geenii.datamodels import AgentCommand, Problem
from geenii.skills import SkillRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])

AGENT_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
AgentScope = Literal["user", "project", "global"]


class AgentSpecInput(pydantic.BaseModel):
    """The frontmatter of an agent spec file: AgentSpec without `file_path` and `scope`, which are set at load time."""
    model_config = pydantic.ConfigDict(extra="forbid")

    name: str
    model: str
    label: str | None = None
    description: str | None = None
    class_name: str | None = None
    system: str | None = None
    model_parameters: dict | None = None
    mcp_servers: list[str] | None = None
    tools: list[str] | None = None
    skills: list[str] | None = None
    working_dir: str | None = None
    allowed_dirs: list[str] | None = None


class AgentCreateRequest(pydantic.BaseModel):
    spec: AgentSpecInput
    instructions: str = ""
    scope: AgentScope = "user"


class AgentUpdateRequest(pydantic.BaseModel):
    spec: AgentSpecInput
    instructions: str = ""


class AgentEnv(pydantic.BaseModel):
    vars: dict[str, str]
    secrets: list[str]  # names only, values are never returned


class SecretValue(pydantic.BaseModel):
    value: str


def dep_agent_registry(request: Request) -> AgentRegistry:
    return request.app.state.agent_registry


def dep_agent_env_store() -> AgentEnvStore:
    return AgentEnvStore()

@router.get("/")
def list_agents(agent_registry: AgentRegistry = Depends(dep_agent_registry)):
    """
    List all configured agents.
    """
    agents = agent_registry.configs.values()
    agents_list = []
    for agent in agents:
        agents_list.append(agent)
    return agents_list


@router.get("/{name}", responses={404: {"model": Problem, "description": "Agent not found"}})
def get_agent(name: str, agent_registry: AgentRegistry = Depends(dep_agent_registry)) -> dict:
    """
    The agent's spec plus its `instructions` (the markdown body of the spec file).
    """
    spec = agent_registry.get_config(name)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found.")
    return _agent_detail(spec)


def _agent_detail(spec: AgentSpec) -> dict:
    try:
        instructions = spec.instructions
    except Exception as e:
        logger.warning(f"Could not read instructions of agent '{spec.name}': {e}")
        instructions = ""
    return {**spec.model_dump(), "instructions": instructions}


def _agent_dir(scope: str) -> Path:
    return Path({s: d for d, s in agent_paths()}[scope])


def _render_spec_file(spec: AgentSpecInput, instructions: str) -> str:
    # empty values are left out, so the file only holds what was set
    front = {k: v for k, v in spec.model_dump().items() if v not in (None, "", [], {})}
    header = yaml.safe_dump(front, sort_keys=False, allow_unicode=True, default_flow_style=False, width=1000)
    body = instructions.strip()
    return f"---\n{header}---\n" + (f"\n{body}\n" if body else "")


def _write_spec_file(path: Path, spec: AgentSpecInput, instructions: str, scope: str,
                     agent_registry: AgentRegistry) -> AgentSpec:
    """Writes the file atomically, then loads it into the registry like load_from_directory() would."""
    content = _render_spec_file(spec, instructions)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            f.write(content)
        os.replace(tmp, path)
    except OSError as e:
        logger.error(f"Could not write agent spec '{path}': {e}")
        raise HTTPException(status_code=500, detail=f"Could not write '{path}': {e.strerror or e}")
    loaded = AgentSpec.from_md_file(str(path))
    loaded.scope = scope
    agent_registry.configs[loaded.name] = loaded
    logger.info(f"Agent spec '{loaded.name}' written to '{path}'.")
    return loaded


@router.post("/", status_code=201, responses={
    400: {"model": Problem, "description": "Invalid agent name"},
    409: {"model": Problem, "description": "Agent or spec file already exists"},
})
def create_agent(request: AgentCreateRequest, agent_registry: AgentRegistry = Depends(dep_agent_registry)) -> dict:
    """
    Create an agent: writes `<agent dir of scope>/<name>.md` and adds it to the registry.
    """
    name = request.spec.name
    if not AGENT_NAME_PATTERN.match(name):
        raise HTTPException(status_code=400, detail="Agent names may only contain letters, digits, - and _.")
    if agent_registry.get_config(name) is not None:
        raise HTTPException(status_code=409, detail=f"Agent '{name}' already exists.")
    path = _agent_dir(request.scope) / f"{name}.md"
    if path.exists():
        raise HTTPException(status_code=409, detail=f"The file '{path}' already exists.")
    return _agent_detail(_write_spec_file(path, request.spec, request.instructions, request.scope, agent_registry))


@router.put("/{name}", responses={
    400: {"model": Problem, "description": "Spec name does not match"},
    404: {"model": Problem, "description": "Agent not found"},
    409: {"model": Problem, "description": "Spec file for a built-in agent already exists"},
})
def update_agent(name: str, request: AgentUpdateRequest,
                 agent_registry: AgentRegistry = Depends(dep_agent_registry)) -> dict:
    """
    Replace an agent's spec file. A built-in agent (no spec file) gets a new file in the user agent directory,
    which replaces it.
    """
    existing = agent_registry.get_config(name)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found.")
    if request.spec.name != name:
        raise HTTPException(status_code=400, detail="Renaming agents is not supported.")
    if existing.file_path:
        path, scope = Path(existing.file_path), existing.scope
    else:
        path, scope = _agent_dir("user") / f"{name}.md", "user"
        if path.exists():
            raise HTTPException(status_code=409, detail=f"The file '{path}' already exists.")
    return _agent_detail(_write_spec_file(path, request.spec, request.instructions, scope, agent_registry))


@router.get("/{name}/commands", responses={404: {"model": Problem, "description": "Agent not found"}})
def list_agent_commands(name: str, agent_registry: AgentRegistry = Depends(dep_agent_registry)) -> list[AgentCommand]:
    """
    Slash commands the agent understands: the built-in commands, then one per configured skill
    ("/<skill>" activates the skill). Commands are listed without the leading slash.
    """
    spec = agent_registry.get_config(name)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found.")

    commands = [AgentCommand(command=c, description=d) for c, d in Agent.BUILTIN_COMMANDS.items()]
    skills = SkillRegistry()
    for skill_name in sorted(spec.skills or []):
        # the macro handler matches lowercased names, and built-in commands win over skills
        if skill_name.lower() in Agent.BUILTIN_COMMANDS:
            logger.warning(f"Skill '{skill_name}' of agent '{name}' is shadowed by the built-in command '/{skill_name.lower()}'.")
            continue
        try:
            skill = skills.load(skill_name)
        except Exception as e:
            logger.warning(f"Skipping skill '{skill_name}' of agent '{name}': {e}")
            continue
        if skill is None:
            continue
        commands.append(AgentCommand(command=skill.name, description=skill.description))
    return commands


def _require_agent(name: str, agent_registry: AgentRegistry) -> None:
    if agent_registry.get_config(name) is None:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found.")


def _agent_env(name: str, env_store: AgentEnvStore) -> AgentEnv:
    return AgentEnv(vars=env_store.get_vars(name), secrets=sorted(env_store.secret_keys(name)))


@router.get("/{name}/env", responses={404: {"model": Problem, "description": "Agent not found"}})
def get_agent_env(name: str, agent_registry: AgentRegistry = Depends(dep_agent_registry),
                  env_store: AgentEnvStore = Depends(dep_agent_env_store)) -> AgentEnv:
    """
    The agent's environment variables, and the names of its secrets. Applies to agent instances created afterwards.
    """
    _require_agent(name, agent_registry)
    return _agent_env(name, env_store)


@router.put("/{name}/env/vars", responses={
    400: {"model": Problem, "description": "Invalid variable name"},
    404: {"model": Problem, "description": "Agent not found"},
})
def set_agent_env_vars(name: str, values: dict[str, str], agent_registry: AgentRegistry = Depends(dep_agent_registry),
                       env_store: AgentEnvStore = Depends(dep_agent_env_store)) -> AgentEnv:
    """
    Replace all environment variables of the agent.
    """
    _require_agent(name, agent_registry)
    try:
        env_store.set_vars(name, values)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return _agent_env(name, env_store)


@router.put("/{name}/env/secrets/{key}", responses={
    400: {"model": Problem, "description": "Invalid secret name"},
    404: {"model": Problem, "description": "Agent not found"},
})
def set_agent_secret(name: str, key: str, secret: SecretValue,
                     agent_registry: AgentRegistry = Depends(dep_agent_registry),
                     env_store: AgentEnvStore = Depends(dep_agent_env_store)) -> AgentEnv:
    """
    Create or replace a secret of the agent.
    """
    _require_agent(name, agent_registry)
    try:
        validate_env_key(key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    env_store.set_secret(name, key, secret.value)
    return _agent_env(name, env_store)


@router.delete("/{name}/env/secrets/{key}", responses={404: {"model": Problem, "description": "Agent or secret not found"}})
def delete_agent_secret(name: str, key: str, agent_registry: AgentRegistry = Depends(dep_agent_registry),
                        env_store: AgentEnvStore = Depends(dep_agent_env_store)) -> AgentEnv:
    """
    Delete a secret of the agent.
    """
    _require_agent(name, agent_registry)
    if not env_store.delete_secret(name, key):
        raise HTTPException(status_code=404, detail=f"Secret '{key}' not found.")
    return _agent_env(name, env_store)
