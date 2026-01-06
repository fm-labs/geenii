import os
import dotenv

dotenv.load_dotenv()
dotenv.load_dotenv(".env.local", override=True)

DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "data")
DATA_DIR = os.environ.get("DATA_DIR", DEFAULT_DATA_DIR)

MCP_CONFIG_FILE="mcpservers.json"

# Completion models
#DEFAULT_COMPLETION_MODEL= "openai:gpt-4o-mini"
DEFAULT_COMPLETION_MODEL= "ollama:mistral:latest"

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