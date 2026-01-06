from geenii.provider.hf.provider import HuggingFaceAIProvider
from geenii.provider.interfaces import AICompletionProvider, AIProvider, AIImageGeneratorProvider, \
    AIAudioGeneratorProvider, AIAudioTranscriptionProvider, AIAudioTranslationProvider
from geenii.provider.ollama.provider import OllamaAIProvider
from geenii.provider.openai.provider import OpenAIProvider
from geenii.util import split_model

type AIProviderType = AICompletionProvider | AIImageGeneratorProvider | AIAudioGeneratorProvider \
                      | AIAudioTranscriptionProvider | AIAudioTranslationProvider | AIProvider

def get_ai_provider(provider: str, iface: type[AIProviderType] = None) -> AIProviderType:
    """
    Get the AI provider instance based on the provider name.

    :param provider: The name of the AI provider (e.g., "ollama", "openai").
    :return: The AIProvider instance for the specified provider.
    """
    if ":" in provider:
        raise ValueError(f"Invalid provider ID format: {provider}. "
                         f"Found unexpected ':' character in provider name. "
                         f"Did you mean to use a model ID? Use 'get_ai_provider_from_model_id' instead.")

    _ai = None
    if provider == "ollama":
        _ai =  OllamaAIProvider()
    elif provider == "openai":
        _ai =  OpenAIProvider()
    elif provider == "hf":
        _ai =  HuggingFaceAIProvider()
    #elif provider == "karl":
    #    return KarlProvider()
    else:
        raise ValueError(f"Unsupported provider: {provider}")

    # check if the provider supports the requested interface
    # the interface is the module name of the provider interface
    if iface is not None and not isinstance(_ai, iface):
        raise RuntimeError(f"Invalid AI: {provider} provider does not support {iface.__name__} interface.")
    return _ai


def get_ai_provider_from_model_id(model_id: str, iface = None) -> tuple[AIProviderType, str, str]:
    """
    Get the AI provider instance based on the model ID.

    :param model_id: The model ID in the format "provider/model_name".
    :return: A tuple containing the AIProvider instance, provider name, and model name.
    """
    if ":" not in model_id:
        raise ValueError(f"Invalid model ID format: {model_id}. Expected 'provider:model_name'.")

    provider_name, model_name = split_model(model_id)
    ai_provider = get_ai_provider(provider_name, iface)
    return ai_provider, provider_name, model_name


def get_ai_completion_provider(model_id: str) -> tuple[AICompletionProvider, str, str]:
    """
    Get the AI completion provider instance based on the provider name.
    """
    return get_ai_provider_from_model_id(model_id, AICompletionProvider)


def get_ai_image_generator_provider(model_id: str) -> tuple[AIImageGeneratorProvider, str, str]:
    """
    Get the AI image generator provider instance based on the provider name.
    """
    return get_ai_provider_from_model_id(model_id, AIImageGeneratorProvider)


def get_ai_audio_generator_provider(model_id: str) -> tuple[AIAudioGeneratorProvider, str, str]:
    """
    Get the AI audio generator provider instance based on the provider name.
    """
    return get_ai_provider_from_model_id(model_id, AIAudioGeneratorProvider)


def get_ai_audio_transcription_provider(model_id: str) -> tuple[AIAudioTranscriptionProvider, str, str]:
    """
    Get the AI audio transcriber provider instance based on the provider name.
    """
    return get_ai_provider_from_model_id(model_id, AIAudioTranscriptionProvider)


def get_ai_audio_translation_provider(model_id: str) -> tuple[AIAudioTranslationProvider, str, str]:
    """
    Get the AI audio transcriber provider instance based on the provider name.
    """
    return get_ai_provider_from_model_id(model_id, AIAudioTranslationProvider)