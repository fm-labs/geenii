import abc
from typing import List, Any, ClassVar

import pydantic

from geenii import settings
from geenii.modelstore import build_model_store


class BaseDatastoreModel(pydantic.BaseModel, abc.ABC):
    uuid : str | None = None

    #COLLECTION_NAME: ClassVar[str] = "my_collection"

    @classmethod
    #@abc.abstractmethod
    def __collection_name(cls) -> str:
        """Returns the collection name for the model class."""
        #return self.__class__.__name__.lower()
        # check if class has COLLECTION_NAME attribute
        if hasattr(cls, "COLLECTION_NAME"):
            return getattr(cls, "COLLECTION_NAME")
        return cls.__name__.lower()

    def save(self):
        """Saves the model instance to the database."""
        store = build_model_store(model_class=self.__class__, collection_name=self.__collection_name())
        return store.create(self)


class BaseAIProviderApiResponse(BaseDatastoreModel):
    id: str
    timestamp: int
    model: str | None = None
    provider: str | None = None
    #output: List[dict] | None = None
    #output_text: str | None = None
    error: str | None = None
    model_result: dict = None

# Completion
class CompletionErrorResponse(BaseDatastoreModel):
    error: str

class CompletionRequest(BaseDatastoreModel):
    prompt: str
    model: str | None = settings.DEFAULT_COMPLETION_MODEL
    system: str | None = None
    # Model tweaking parameters
    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None
    # Output format
    output_format: str | None = None
    # Streaming support
    stream: bool | None = False

class CompletionResponse(BaseAIProviderApiResponse):

    COLLECTION_NAME: ClassVar[str] = "completions"

    prompt: str
    output: List[dict] | None = None
    output_text: str | None = None


# Assistant
class AssistantCompletionRequest(CompletionRequest):
    # Tooling support
    tools: List[str] | None = None
    # Context ID for the completion request
    context_id: str | None = None

class AssistantCompletionResponse(CompletionResponse):
    prompt: str
    # The response may include additional information about the tools used
    tools_used: List[str] | None = None
    # The context ID for the completion request
    context_id: str | None = None


# Image Generation
class ImageGenerationApiRequest(BaseDatastoreModel):
    prompt: str
    model: str | None = settings.DEFAULT_IMAGE_GENERATION_MODEL
    # Model tweaking parameters
    size: str | None = "1024x1024"  # Default image size
    #style: str | None = None  # Optional style parameter
    # Output format
    response_format: str | None = None # "b64_json" or "url"

class ImageGenerationApiResponse(BaseAIProviderApiResponse):
    prompt: str
    output: List[dict] | None = None # contains either 'base64' or 'url' keys
    #url: str | None = None  # URL to the generated audio file
    #base64: str | None = None  # Base64 encoded audio data, if applicable


# Audio Generation
class AudioGenerationApiRequest(BaseDatastoreModel):
    model: str | None = settings.DEFAULT_AUDIO_GENERATION_MODEL
    text: str
    # Model tweaking parameters
    duration: int | None = 30  # Default duration in seconds
    sample_rate: int | None = 44100  # Default sample rate in Hz
    voice: str | None = None  # Optional voice parameter
    speed: float | None = 1.0  # Default speech speed

class AudioGenerationApiResponse(BaseAIProviderApiResponse):
    text: str
    output: List[dict] | None = None # contains either 'base64' or 'url' keys
    #url: str | None = None  # URL to the generated audio file
    #base64: str | None = None  # Base64 encoded audio data, if applicable


# Audio Transcription
class AudioTranscriptionApiRequest(BaseDatastoreModel):
    model: str | None = settings.DEFAULT_AUDIO_TRANSCRIPTION_MODEL
    input_file: str  # Path to the audio file to be transcribed
    input_blob: bytes | None = None  # Optional raw audio data
    source_lang: str | None = "en"  # Default source language

class AudioTranscriptionApiResponse(BaseAIProviderApiResponse):
    output_text: str | None = None  # Transcribed text from the audio


# Audio Translation
class AudioTranslationApiRequest(BaseDatastoreModel):
    model: str | None = settings.DEFAULT_AUDIO_TRANSLATION_MODEL
    input_file: str  # Path to the audio file to be translated
    source_lang: str | None = "en"  # Default source language
    target_lang: str | None = "de"  # Default target language

class AudioTranslationApiResponse(BaseAIProviderApiResponse):
    output_text: str | None = None  # Translated text from the audio


# MCP
class MCPToolCallRequest(BaseDatastoreModel):
    #server_name: str
    tool_name: str
    arguments: dict # | None = pydantic.Field(default_factory=dict)

class MCPToolCallResponse(MCPToolCallRequest):
    result: dict | list | str | Any | None = None
    error: str | None = None

class MCPServerConfig(BaseDatastoreModel):
    name: str
    url: str | None = None
    command: str | None = None
    args: List[str] | None = pydantic.Field(default_factory=list)
    env: dict[str, str] | None = pydantic.Field(default_factory=dict)

class MCPServerInfo(BaseDatastoreModel):
    name: str
    status: str | None = None
    description: str | None = None
    tools: List[dict] | None = pydantic.Field(default_factory=list)
    resources: List[dict] | None = pydantic.Field(default_factory=list)
    prompts: List[dict] | None = pydantic.Field(default_factory=list)