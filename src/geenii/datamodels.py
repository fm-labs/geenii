import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

import pydantic

from geenii import config
from geenii.chat_models import ContentPart, TextContent


class AIProviderInfo(pydantic.BaseModel):
    name: str
    configured: bool = False
    # description: str | None = None
    # website: str | None = None
    # models: List[str] | None = pydantic.Field(default_factory=list)


class AIModelInfo(pydantic.BaseModel):
    provider: str
    name: str
    locality: Literal["local", "cloud", "mixed"]  # "local" or "cloud"
    description: str | None = None
    capabilities: list[str] | None = pydantic.Field(default_factory=list)
    metadata: dict | None = pydantic.Field(default_factory=dict)
    installed: bool = False


# Version of the usage convention in the usage log (`usage_version` of a line). Lines without it are version 1,
# where anthropic's input_tokens did not include cache reads and writes.
USAGE_VERSION = 2


class Usage(pydantic.BaseModel):
    """
    Token usage of one completion, normalised across providers.

    - `input_tokens` counts *all* input tokens the model processed, cached or not.
    - `cache_read_input_tokens` / `cache_creation_input_tokens` are the parts of `input_tokens` read from / written
      to the prompt cache; None if the provider does not report them.
    - `total_tokens` is input + output (so it includes cached input).

    Providers map their own counts to this convention. Fields a provider does not report stay None;
    `model_dump(exclude_none=True)` is the form written to the usage log.
    """

    model_config = pydantic.ConfigDict(extra="ignore")  # tolerate unknown keys, e.g. when reading old log lines

    input_tokens: int = 0
    output_tokens: int = 0
    # input + output when not given; providers that report their own total may pass it
    total_tokens: int | None = None
    # prompt caching: parts of input_tokens (anthropic: both; openai: reads only)
    cache_creation_input_tokens: int | None = None
    cache_read_input_tokens: int | None = None
    # timings in milliseconds (ollama)
    load_duration: int | None = None
    input_duration: int | None = None
    output_duration: int | None = None
    total_duration: int | None = None

    @pydantic.model_validator(mode="after")
    def _default_total(self):
        if self.total_tokens is None:
            self.total_tokens = self.input_tokens + self.output_tokens
        return self

    def __add__(self, other: "Usage") -> "Usage":
        """Sum of two usages. An optional field stays None only if it is None on both sides."""
        if not isinstance(other, Usage):
            return NotImplemented
        summed = {}
        for name in type(self).model_fields:
            a, b = getattr(self, name), getattr(other, name)
            summed[name] = None if a is None and b is None else (a or 0) + (b or 0)
        return Usage(**summed)

    @property
    def uncached_input_tokens(self) -> int:
        """Input tokens neither read from nor written to the prompt cache."""
        return self.input_tokens - (self.cache_read_input_tokens or 0) - (self.cache_creation_input_tokens or 0)

    @classmethod
    def from_log_entry(cls, entry: dict) -> "Usage":
        """
        The usage of a usage log line, converted to the current convention.
        Raises pydantic.ValidationError if the line's usage is malformed.
        """
        usage = cls.model_validate(entry.get("usage") or {})
        if entry.get("usage_version") is None and entry.get("provider") == "anthropic":
            # version 1: anthropic's input_tokens (and so total_tokens) left out the cached input
            cached = (usage.cache_read_input_tokens or 0) + (usage.cache_creation_input_tokens or 0)
            usage.input_tokens += cached
            usage.total_tokens += cached
        return usage


class ModelMessage(pydantic.BaseModel):
    type: Literal["message"] = "message"
    role: str  # e.g., "user", "assistant", "system"
    content: list[ContentPart] = pydantic.Field(default_factory=list)
    id: str = pydantic.Field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: datetime = pydantic.Field(default_factory=lambda: datetime.now(UTC))
    # Token usage of the model call that produced this message. Only the *first* message created from a
    # completion response carries it (a response with several tool calls becomes several messages), so summing
    # over a conversation's messages counts every call once. None for user, tool and generated messages.
    usage: Usage | None = None

    def to_text(self) -> str:
        return "\n".join(part.to_text() for part in self.content)

    def to_json(self) -> str:
        return self.model_dump_json()

    def to_dict(self) -> dict:
        return self.model_dump(mode="python")


class SystemMessage(pydantic.BaseModel):
    type: Literal["system"] = "system"
    role: str = "system"
    level: Literal["info", "warning", "error"] = "info"
    content: list[ContentPart] = pydantic.Field(default_factory=list)
    id: str = pydantic.Field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: datetime = pydantic.Field(default_factory=lambda: datetime.now(UTC))

    def to_text(self) -> str:
        return "\n".join(part.to_text() for part in self.content)

    def to_json(self) -> str:
        return self.model_dump_json()

    def to_dict(self) -> dict:
        return self.model_dump(mode="python")

    @classmethod
    def from_text(cls, text: str) -> "SystemMessage":
        return cls(content=[TextContent(text=text)])


# class StreamMessage(pydantic.BaseModel):
#     type: str = "stream"
#     content: list[ContentPart] = pydantic.Field(default_factory=list)


WireMessage = Annotated[
    SystemMessage | ModelMessage,
    pydantic.Field(discriminator="type"),
]

# class WireMessageProtocol(Protocol):
#     def to_text(self) -> str: ...
#     def to_json(self) -> dict[str, Any]: ...
#     def to_dict(self) -> dict[str, Any]: ...


class AgentCommand(pydantic.BaseModel):
    """A slash command an agent understands (sent as "/<command> [args]")."""

    command: str  # without the leading slash
    description: str = ""


class ChatMessage(pydantic.BaseModel):
    """Chat message envelope"""

    id: str = pydantic.Field(default_factory=lambda: uuid.uuid4().hex)
    timestamp: datetime = pydantic.Field(default_factory=lambda: datetime.now(UTC))
    sender_id: str
    message: WireMessage
    context_id: str | None = None


# Chat stream events (NDJSON lines of POST /chats/{context_id}/messages)


class ChatMessageEvent(pydantic.BaseModel):
    type: Literal["message"] = "message"
    message: ChatMessage


class ChatStatusEvent(pydantic.BaseModel):
    type: Literal["status"] = "status"
    status: Literal["thinking", "tool", "awaiting_input"]


class ChatErrorEvent(pydantic.BaseModel):
    type: Literal["error"] = "error"
    error: str


class ChatDoneEvent(pydantic.BaseModel):
    type: Literal["done"] = "done"


ChatStreamEvent = Annotated[
    ChatMessageEvent | ChatStatusEvent | ChatErrorEvent | ChatDoneEvent,
    pydantic.Field(discriminator="type"),
]

# Completion


class CompletionErrorResponse(pydantic.BaseModel):
    error: str


class CompletionRequest(pydantic.BaseModel):
    prompt: str
    model: str = config.DEFAULT_COMPLETION_MODEL
    system: list[str] | None = None
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
    model_result: dict | None = None


class CompletionResponse(BaseCompletionResponse):
    # prompt: str
    output: list[ContentPart] | None = None
    output_text: str | None = None
    reasoning_output: str | None = None
    # Token usage; None if the provider did not report any
    usage: Usage | None = None


# Chat completion
class ChatCompletionRequest(CompletionRequest):
    # Conversation history (for chat completions)
    messages: list[ModelMessage] | None = None
    # Tooling support
    tools: set[str] | None = None
    # Context ID for the completion request
    context_id: str | None = None


class ChatCompletionResponse(CompletionResponse):
    prompt: str  # todo deprecated
    # The response may include additional information about the tools used
    tools_used: list[str] | None = None
    # The context ID for the completion request
    context_id: str | None = None


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
    output: list[ContentPart] | None = None  # contains either 'base64' or 'url' keys
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


class AudioSpeechGenerationApiResponse(BaseCompletionResponse):
    text: str
    output: list[dict] | None = None  # contains either 'base64' or 'url' keys
    url: str | None = None  # URL to the generated audio file
    base64: str | None = None  # Base64 encoded audio data, if applicable


# Audio Transcription
class AudioTranscriptionApiRequest(pydantic.BaseModel):
    model: str | None = config.DEFAULT_AUDIO_TRANSCRIPTION_MODEL
    input_file: str = None  # Path to the audio file to be transcribed
    input_blob: bytes | None = None  # Audio data as bytes (alternative to input_file)
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
    args: list[str] | None = pydantic.Field(default_factory=list)
    env: dict[str, str] | None = pydantic.Field(default_factory=dict)


class MCPServerInfo(pydantic.BaseModel):
    name: str
    status: str | None = None
    description: str | None = None
    tools: list[dict] | None = pydantic.Field(default_factory=list)
    resources: list[dict] | None = pydantic.Field(default_factory=list)
    prompts: list[dict] | None = pydantic.Field(default_factory=list)


# Standard error model (Problem Details, RFC 7807)
class Problem(pydantic.BaseModel):
    error: str = pydantic.Field(..., description="Short, human-readable summary of the problem type")
    status: int = pydantic.Field(..., description="HTTP status code")
    detail: str | None = pydantic.Field(None, description="Human-readable explanation specific to this occurrence")
    # problem_type: str = pydantic.Field(default="about:blank", description="URI identifying the problem type")
    # instance: Optional[str] = Field(None, description="URI reference that identifies the specific occurrence")
    # errors: Optional[dict[str, Any]] = Field(
    #    None, description="Optional field for validation or field-specific errors"
    # )
