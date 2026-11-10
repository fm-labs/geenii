from __future__ import annotations

import json
import os
from os.path import realpath
from pathlib import Path

import dotenv

from geenii.utils.os_util import get_user_home_dir

APP_VERSION = "0.3.4"

GEENII_USER_HOME = get_user_home_dir()
GEENII_WORKING_DIR = realpath(os.environ.get("GEENII_WORKING_DIR", os.getcwd()))

GEENII_CHAT_SESSIONS_DIR = Path(GEENII_USER_HOME) / ".geenii" / "chats"

# Load environment variables from the project and user .env files, if they exist.
# Without override the first source to set a variable wins: shell > project .env > user .env
dotenv.load_dotenv(
    os.path.join(GEENII_WORKING_DIR, ".geenii", ".env"), override=False, verbose=True
)
dotenv.load_dotenv(
    os.path.join(GEENII_USER_HOME, ".geenii", ".env"), override=False, verbose=True
)

GEENII_CACHE_DIR = os.environ.get(
    "GEENII_CACHE_DIR", os.path.join(GEENII_USER_HOME, ".cache", "geenii")
)
GEENII_CACHE_DISABLED = (
    os.environ.get("GEENII_CACHE_DISABLED", "false").lower() == "true"
)

# Default minimum age (seconds since a process finished) before the process manager's gc removes it
PM_GC_MAX_AGE = float(os.environ.get("GEENII_PM_GC_MAX_AGE", 7 * 24 * 3600))

# GEENII_BIN = os.getenv("GEENII_BIN", "geenii")

# Static web GUI served by the API server (defaults to the repo's www/ folder)
WWW_DIR = os.environ.get(
    "GEENII_WWW_DIR",
    os.path.join(os.path.dirname(__file__), os.pardir, os.pardir, "www"),
)

GEENII_MEMORY_ENGINE = "file"

FERNET_SECRET_KEY = os.environ.get("FERNET_SECRET_KEY", "")

MCP_CONFIG_FILE = "mcp.json"
MCP_INIT_TIMEOUT = float(os.environ.get("GEENII_MCP_INIT_TIMEOUT", "30"))

# Completion models
# DEFAULT_COMPLETION_MODEL= "openai:gpt-4o-mini"
DEFAULT_COMPLETION_MODEL = "ollama:qwen3:8b"

# Image generation
# DEFAULT_IMAGE_GENERATION_MODEL="stable-diffusion:stable-diffusion:latest" # need GPU
DEFAULT_IMAGE_GENERATION_MODEL = "openai:dall-e-2"

# Audio generation / Text-to-Speech
DEFAULT_AUDIO_GENERATION_MODEL = "hf:llama-2:latest"
# Audio transcription / Speech-to-Text
# DEFAULT_AUDIO_TRANSCRIPTION_MODEL="whisper:whisper-1:latest"
DEFAULT_AUDIO_TRANSCRIPTION_MODEL = "openai:whisper-1"
DEFAULT_AUDIO_TRANSLATION_MODEL = "whisper:whisper-1:latest"

WHISPERCPP_IMAGE = "whispercpp:latest"

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

OLLAMA_HOST = os.environ.get(
    "OLLAMA_HOST", "http://localhost:11434"
)  # default Ollama API endpoint
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", "")

# Database settings
MONGODB_URI = os.environ.get("MONGODB_URI", "")
MONGODB_DB_NAME = os.environ.get("MONGODB_DB_NAME", "geenii_brain0")

# Redis settings
REDIS_URI = os.environ.get("REDIS_URI", "")

# ### Chat settings ###
# # Path to the SQLite database file for storing chat history and related data
# CHAT_DB_PATH = os.environ.get("GEENII_CHAT_DB_PATH", f"{CACHE_DIR}/chat.db")
#
# # A unique namespace UUID for generating deterministic UUIDs for DM room IDs.
# CHAT_DM_NAMESPACE =  os.environ.get("GEENII_CHAT_DM_NAMESPACE", "a7f3c2e1-4b8d-5a9f-8c3e-2d1b6f0e4a7c")
# CHAT_GROUP_NAMESPACE =  os.environ.get("GEENII_CHAT_GROUP_NAMESPACE", "b7f3c2e1-8b4d-5a9f-8c3e-2d1b6f0e4a7a")


# def get_user_dir():
#     if not os.path.exists(GEENII_DIR):
#         os.makedirs(GEENII_DIR, exist_ok=True)
#     return GEENII_DIR
#
#
# def get_data_dir():
#     #home_dir = get_user_home_dir()
#     #user_dir = os.path.join(home_dir, ".geenii")
#     #if not os.path.exists(user_dir):
#     #    os.makedirs(user_dir, exist_ok=True)
#     #return user_dir
#     if not os.path.exists(GEENII_DATA_DIR):
#         os.makedirs(GEENII_DATA_DIR, exist_ok=True)
#     return GEENII_DATA_DIR


def read_user_settings():
    user_settings_path = os.path.join(GEENII_USER_HOME, ".geenii", "settings.json")
    default_settings = {
        "theme": "system",  # options: "light", "dark", "system"
        "notifications": True,
        "language": "en-US",
        "environment": {},
        "skill_dirs": [],
        "projects": {},  # "/path/to/project/dir": {"trusted": true}
    }
    if os.path.exists(user_settings_path):
        try:
            with open(user_settings_path, "r") as f:
                settings = json.load(f)
                return settings
        except Exception as e:
            print(f"Error reading user settings: {e}")
            return default_settings
    else:
        return default_settings


def write_user_settings(settings: dict):
    print(f"Saving settings: {settings}")
    user_settings_path = os.path.join(GEENII_USER_HOME, ".geenii", "settings.json")
    try:
        with open(user_settings_path, "w") as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        print(f"Error writing user settings: {e}")


def _normalize_dir(path: str) -> str:
    return realpath(os.path.expanduser(path))


def get_projects() -> dict[str, dict]:
    """The `projects` section of the user settings, keyed by the resolved project directory.
    Project directories must be absolute paths; others are skipped."""
    projects = read_user_settings().get("projects") or {}
    result = {}
    for d, conf in projects.items():
        if not os.path.isabs(d):
            print(
                f"Warning: Project directory '{d}' is not an absolute path, ignoring it."
            )
            continue
        result[realpath(d)] = conf or {}
    return result


def project_paths() -> list[str]:
    """The configured project directories (resolved, absolute)."""
    return list(get_projects())


def get_project_dir(path: str) -> str | None:
    """The project directory that contains the path (or is the path itself), or None.
    With nested projects the innermost one wins."""
    target = Path(_normalize_dir(path))
    matches = [d for d in get_projects() if target.is_relative_to(d)]
    return max(matches, key=len, default=None)


def is_project_dir(path: str) -> bool:
    """Whether the directory is registered as a project in the user settings."""
    return _normalize_dir(path) in get_projects()


def is_project_dir_trusted(path: str) -> bool:
    """Whether the directory is a registered project marked as `"trusted": true`."""
    return get_projects().get(_normalize_dir(path), {}).get("trusted", False) is True


def makedirs_safe(path: str):
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        print(f"Error creating directory {path}: {e}")


def make_app_directories():
    # ensure internal directories exist
    makedirs_safe(f"{GEENII_CACHE_DIR}")
    makedirs_safe(f"{GEENII_CACHE_DIR}/logs")


def agent_paths() -> list[tuple[str, str]]:
    return [
        (os.path.join(GEENII_WORKING_DIR, ".geenii", "agents"), "project"),
        (os.path.join(GEENII_USER_HOME, ".geenii", "agents"), "user"),
        ("/var/geenii/agents", "global"),
    ]


def get_root_mcp_config_path() -> Path:
    """The user-level mcp.json; the base config that the working dir mcp.json overrides."""
    return Path(GEENII_USER_HOME) / ".geenii" / MCP_CONFIG_FILE


def get_mcp_config_paths() -> list[Path]:
    """All mcp.json files, in the order they are merged (later files win)."""
    return [
        get_root_mcp_config_path(),
        Path(GEENII_WORKING_DIR) / ".geenii" / MCP_CONFIG_FILE,
    ]


def skill_paths() -> list[str]:
    _skill_paths = [
        os.path.join(GEENII_WORKING_DIR, ".geenii", "skills"),
        os.path.join(GEENII_USER_HOME, ".geenii", "skills"),
    ]
    _settings = read_user_settings()
    for skill_dir in _settings.get("skill_dirs", []):
        if os.path.isdir(skill_dir):
            _skill_paths.append(skill_dir)
        else:
            print(
                f"Warning: Skill directory '{skill_dir}' does not exist or is not a directory."
            )

    # remove duplicates
    _skill_paths = list(dict.fromkeys(_skill_paths))
    return _skill_paths


def flow_dirs() -> list[str]:
    """Directories flows are loaded from: the user's, then the working directory's (without duplicates)"""
    dirs = [
        Path(GEENII_USER_HOME, ".geenii", "flows"),
        Path(GEENII_WORKING_DIR, ".geenii", "flows"),
    ]
    return list(dict.fromkeys(str(d.resolve()) for d in dirs))


def apps_dirs() -> list[str]:
    return [
        os.path.join(GEENII_USER_HOME, ".geenii", "apps"),
        os.path.join(GEENII_WORKING_DIR, ".geenii", "apps"),
    ]


def project_skills_dir() -> str:
    """Where `geenii skills install` puts skills"""
    return os.path.join(GEENII_WORKING_DIR, ".geenii", "skills")
