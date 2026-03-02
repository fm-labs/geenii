import uuid
from datetime import datetime, UTC
from typing import List, Any, Set, Literal

import pydantic
from fastapi import UploadFile

from geenii import config
from geenii.chat.chat_models import ContentPart


class AIProviderInfo(pydantic.BaseModel):
    name: str
    #description: str | None = None
    #website: str | None = None
    #models: List[str] | None = pydantic.Field(default_factory=list)

class AIModelInfo(pydantic.BaseModel):
    provider: str
    name: str
    locality: Literal["local","cloud","mixed"]  # "local" or "cloud"
    description: str | None = None
    capabilities: List[str] | None = pydantic.Field(default_factory=list)
    metadata: dict | None = pydantic.Field(default_factory=dict)


class ModelMessage(pydantic.BaseModel):
    type: str = "message"
    role: str  # e.g., "user", "assistant", "system"
    content: list[ContentPart] = pydantic.Field(default_factory=list)
    id: str = pydantic.Field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: datetime = pydantic.Field(default_factory=lambda: datetime.now(UTC))

    def to_text(self) -> str:
        return "\n".join(part.to_text() for part in self.content)

    def to_json(self) -> str:
        return self.model_dump_json()

    def to_dict(self) -> dict:
        return self.model_dump(mode="python")

# Completion

class CompletionErrorResponse(pydantic.BaseModel):
    error: str


class CompletionRequest(pydantic.BaseModel):
    prompt: str
    model: str | None = config.DEFAULT_COMPLETION_MODEL
    system: List[str] | None = None
    # Model tweaking parameters
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    # Output format
    output_format: str | None = None
    output_schema: dict | None = None
    # Streaming support
    stream: bool | None = False
    model_parameters: dict | None = pydantic.Field(default_factory=dict)


class BaseCompletionResponse(pydantic.BaseModel):
    id: str
    timestamp: int
    model: str | None = None
    # provider: str | None = None
    # output: List[dict] | None = None
    # output_text: str | None = None
    error: str | None = None
    model_result: dict = None

class CompletionResponse(BaseCompletionResponse):
    # prompt: str
    output: List[ContentPart] | None = None
    output_text: str | None = None
    reasoning_output: str | None = None


# Chat completion
class ChatCompletionRequest(CompletionRequest):
    # Conversation history (for chat completions)
    messages: List[ModelMessage] | None = None
    # Tooling support
    tools: Set[str] | None = None
    # Context ID for the completion request
    context_id: str | None = None


class ChatCompletionResponse(CompletionResponse):
    prompt: str # todo deprecated
    # The response may include additional information about the tools used
    tools_used: List[str] | None = None
    # The context ID for the completion request
    context_id: str | None = None
    # Usage stats dict
    usage: dict | None = pydantic.Field(default_factory=dict)


# Image Generation
class ImageGenerationApiRequest(pydantic.BaseModel):
    prompt: str
    model: str | None = config.DEFAULT_IMAGE_GENERATION_MODEL
    # Model tweaking parameters
    size: str | None = "1024x1024"  # Default image size
    # style: str | None = None  # Optional style parameter
    # Output format
    response_format: str | None = None  # "b64_json" or "url"


class ImageGenerationApiResponse(BaseCompletionResponse):
    prompt: str
    output: List[dict] | None = None  # contains either 'base64' or 'url' keys
    # url: str | None = None  # URL to the generated audio file
    # base64: str | None = None  # Base64 encoded audio data, if applicable


# Audio Generation
class AudioGenerationApiRequest(pydantic.BaseModel):
    model: str | None = config.DEFAULT_AUDIO_GENERATION_MODEL
    text: str
    # Model tweaking parameters
    duration: int | None = 30  # Default duration in seconds
    sample_rate: int | None = 44100  # Default sample rate in Hz
    voice: str | None = None  # Optional voice parameter
    speed: float | None = 1.0  # Default speech speed


class AudioGenerationApiResponse(BaseCompletionResponse):
    text: str
    output: List[dict] | None = None  # contains either 'base64' or 'url' keys
    # url: str | None = None  # URL to the generated audio file
    # base64: str | None = None  # Base64 encoded audio data, if applicable


# Audio Transcription
class AudioTranscriptionApiRequest(pydantic.BaseModel):
    model: str | None = config.DEFAULT_AUDIO_TRANSCRIPTION_MODEL
    input_file: str = None  # Path to the audio file to be transcribed
    input_blob: UploadFile | None = None  # File(...)  # Optional audio file as blob
    source_lang: str | None = "en"  # Default source language


class AudioTranscriptionApiResponse(BaseCompletionResponse):
    output_text: str | None = None  # Transcribed text from the audio


# Audio Translation
class AudioTranslationApiRequest(pydantic.BaseModel):
    model: str | None = config.DEFAULT_AUDIO_TRANSLATION_MODEL
    input_file: str  # Path to the audio file to be translated
    source_lang: str | None = "en"  # Default source language
    target_lang: str | None = "de"  # Default target language


class AudioTranslationApiResponse(BaseCompletionResponse):
    output_text: str | None = None  # Translated text from the audio


# MCP
class MCPToolCallRequest(pydantic.BaseModel):
    # server_name: str
    tool_name: str
    arguments: dict  # | None = pydantic.Field(default_factory=dict)


class MCPToolCallResponse(MCPToolCallRequest):
    result: dict | list | str | Any | None = None
    error: str | None = None


class MCPServerConfig(pydantic.BaseModel):
    name: str
    url: str | None = None
    command: str | None = None
    args: List[str] | None = pydantic.Field(default_factory=list)
    env: dict[str, str] | None = pydantic.Field(default_factory=dict)


class MCPServerInfo(pydantic.BaseModel):
    name: str
    status: str | None = None
    description: str | None = None
    tools: List[dict] | None = pydantic.Field(default_factory=list)
    resources: List[dict] | None = pydantic.Field(default_factory=list)
    prompts: List[dict] | None = pydantic.Field(default_factory=list)
