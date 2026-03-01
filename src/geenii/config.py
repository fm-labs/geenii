import os
import dotenv
import json

from geenii.utils.os_util import get_user_home, get_user_home_dir

APP_VERSION = "0.2.0"

USER_HOME_DIR = get_user_home()
DATA_DIR = os.environ.get("DATA_DIR", USER_HOME_DIR + "/.geenii")
CACHE_DIR = os.environ.get("CACHE_DIR", DATA_DIR + "/cache")
CACHE_DISABLED = os.environ.get("CACHE_DISABLED", "true").lower() == "true"

dotenv.load_dotenv(DATA_DIR + "/.env")

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
#DEFAULT_AUDIO_TRANSCRIPTION_MODEL="whisper:whisper-1:latest"
DEFAULT_AUDIO_TRANSCRIPTION_MODEL="openai:whisper-1"
DEFAULT_AUDIO_TRANSLATION_MODEL="whisper:whisper-1:latest"

WHISPERCPP_IMAGE="whispercpp:latest"

OPENAI_API_KEY=os.environ.get("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY=os.environ.get("ANTHROPIC_API_KEY", "")

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://localhost:11434")  # default Ollama API endpoint
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", "")

# Database settings
MONGODB_URI = os.environ.get("MONGODB_URI", "")
MONGODB_DB_NAME = os.environ.get("MONGODB_DB_NAME", "geenii_brain0")

# Redis settings
REDIS_URI = os.environ.get("REDIS_URI", "")


### Chat settings ###
# Path to the SQLite database file for storing chat history and related data
CHAT_DB_PATH = os.environ.get("CHAT_DB_PATH", f"{DATA_DIR}/chat.db")

# A unique namespace UUID for generating deterministic UUIDs for DM room IDs.
CHAT_DM_NAMESPACE = "a7f3c2e1-4b8d-5a9f-8c3e-2d1b6f0e4a7c"
CHAT_GROUP_NAMESPACE = "b7f3c2e1-8b4d-5a9f-8c3e-2d1b6f0e4a7a"


def get_user_data_dir():
    #home_dir = get_user_home_dir()
    #user_dir = os.path.join(home_dir, ".geenii")
    #if not os.path.exists(user_dir):
    #    os.makedirs(user_dir, exist_ok=True)
    #return user_dir
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)
    return DATA_DIR


def read_user_settings():
    user_settings_path = os.path.join(get_user_data_dir(), "settings.json")
    default_settings = {
        "theme": "dark",
        "notifications": True,
        "language": "en-US"
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
    user_settings_path = os.path.join(get_user_data_dir(), "settings.json")
    try:
        with open(user_settings_path, "w") as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        print(f"Error writing user settings: {e}")
