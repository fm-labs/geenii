import abc
from typing import List

from geenii.datamodels import CompletionResponse, ImageGenerationApiResponse, AudioTranscriptionApiResponse, \
    AudioGenerationApiResponse, AudioTranslationApiResponse


class AIProvider(abc.ABC):
    """Abstract base class for AI providers."""

    def __init__(self, name: str):
        self.name = name

    def __str__(self):
        return self.name

    def __repr__(self):
        return f"AIProvider(name={self.name})"

    @abc.abstractmethod
    def get_capabilities(self) -> list[str]:
        """Return a list of capabilities provided by this AI provider"""
        pass

    @abc.abstractmethod
    def get_models(self) -> list[str]:
        """Return a list of models available in this AI provider"""
        pass


class AICompletionProvider(abc.ABC):
    """Abstract base class for AI completion providers.
    This class defines the interface for AI completion providers, which can be used to
    get completions based on a given prompt.
    """
    @abc.abstractmethod
    def generate_completion(self, prompt: str, **kwargs) -> CompletionResponse:
        """Get an AI completion for the given prompt"""
        pass


class ChatCompletionProvider(abc.ABC):
    """Abstract base class for AI chat completion providers.
    This class defines the interface for AI chat completion providers, which can be used to
    get chat completions based on a series of messages and a prompt.
    """
    @abc.abstractmethod
    def generate_chat_completion(self, prompt: str, messages: list, **kwargs):
        """Get an AI chat completion for the given messages"""
        pass


class AIAssistantProvider(abc.ABC):
    """Abstract base class for AI tool calling providers.
    This class defines the interface for AI tool calling providers, which can be used to
    get tool call completions based on a prompt and a list of tools.
    """
    @abc.abstractmethod
    def generate_assistant_completion(self, prompt: str, tool_names: List[str], **kwargs):
        """Get an AI assistant completion with tooling support for the given prompt and tools"""
        pass


class AIImageGeneratorProvider(abc.ABC):
    """Abstract base class for AI image generation providers.
    This class defines the interface for AI image generation providers, which can be used to
    generate images based on a given prompt.
    """
    @abc.abstractmethod
    def generate_image(self, prompt: str, **kwargs) -> ImageGenerationApiResponse:
        """Generate an image based on the given prompt"""
        pass


class AIAudioGeneratorProvider(abc.ABC):
    """Abstract base class for AI text-to-speech providers.
    This class defines the interface for AI text-to-speech providers, which can be used to
    convert text into speech.
    """
    @abc.abstractmethod
    def generate_speech(self, text: str, **kwargs) -> AudioGenerationApiResponse:
        """Convert the given text into speech"""
        pass


class AIAudioTranscriptionProvider(abc.ABC):
    """Abstract base class for AI speech-to-text providers.
    This class defines the interface for AI speech-to-text providers, which can be used to
    convert speech into text.
    """
    @abc.abstractmethod
    def generate_audio_transcription(self, audio: bytes | str, **kwargs) -> AudioTranscriptionApiResponse:
        """Convert the given audio into text"""
        pass


class AIAudioTranslationProvider(abc.ABC):
    """Abstract base class for AI audio translation providers.
    This class defines the interface for AI audio translation providers, which can be used to
    translate audio from one language to another.
    """
    @abc.abstractmethod
    def generate_audio_translation(self, audio: bytes | str, target_language: str, **kwargs) -> AudioTranslationApiResponse:
        """Translate the given audio into the target language"""
        pass


# class AITextTranslationProvider(abc.ABC):
#     """Abstract base class for AI text translation providers.
#     This class defines the interface for AI text translation providers, which can be used to
#     translate text from one language to another.
#     """
#     @abc.abstractmethod
#     def generate_text_translation(self, text: str, target_language: str, **kwargs):
#         """Translate the given text into the target language"""
#         pass