import os
import dotenv

dotenv.load_dotenv()
dotenv.load_dotenv(".env.local", override=True)

APP_VERSION = "0.1.4"

def get_os_name() -> str:
    platform = os.environ.get("PLATFORM", "").lower()
    if platform in ("windows", "linux", "darwin"):
        return platform
    # Fallback to sys.platform if PLATFORM env var is not set or unrecognized
    import sys
    if sys.platform.startswith("win"):
        return "windows"
    elif sys.platform.startswith("linux"):
        return "linux"
    elif sys.platform.startswith("darwin"):
        return "darwin"
    else:
        return "unknown"

def get_user_home() -> str:
    if get_os_name() == "windows":
        return os.environ.get("USERPROFILE", "")
    else:
        return os.environ.get("HOME", "")


USER_HOME_DIR = get_user_home()
DATA_DIR = os.environ.get("DATA_DIR", USER_HOME_DIR + "/.geenii")
CACHE_DIR = os.environ.get("CACHE_DIR", DATA_DIR + "/cache")

MCP_CONFIG_FILE="mcp.json"

# Completion models
#DEFAULT_COMPLETION_MODEL= "openai:gpt-4o-mini"
DEFAULT_COMPLETION_MODEL="ollama:qwen3:8b"

# Image generation
#DEFAULT_IMAGE_GENERATION_MODEL="stable-diffusion:stable-diffusion:latest" # need GPU
DEFAULT_IMAGE_GENERATION_MODEL="openai:dall-e-2"

# Audio generation / Text-to-Speech
DEFAULT_AUDIO_GENERATION_MODEL="hf:llama-2:latest"
# Audio transcription / Speech-to-Text
DEFAULT_AUDIO_TRANSCRIPTION_MODEL="whisper:whisper-1:latest"
DEFAULT_AUDIO_TRANSLATION_MODEL="whisper:whisper-1:latest"

WHISPERCPP_IMAGE="whispercpp:latest"

OPENAI_API_KEY=os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY=os.environ.get("ANTHROPIC_API_KEY", "")


# Database settings
MONGODB_URI = os.environ.get("MONGODB_URI", "")
MONGODB_DB_NAME = os.environ.get("MONGODB_DB_NAME", "geenii_brain0")

# Redis settings
REDIS_URI = os.environ.get("REDIS_URI", "")


### Chat settings ###
# Path to the SQLite database file for storing chat history and related data
CHAT_DB_PATH = "./data/chat.db"

# A unique namespace UUID for generating deterministic UUIDs for DM room IDs.
CHAT_DM_NAMESPACE = "a7f3c2e1-4b8d-5a9f-8c3e-2d1b6f0e4a7c"
CHAT_GROUP_NAMESPACE = "b7f3c2e1-8b4d-5a9f-8c3e-2d1b6f0e4a7a"


