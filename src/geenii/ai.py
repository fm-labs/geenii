from geenii.datamodels import CompletionRequest, CompletionResponse, CompletionErrorResponse, \
    ChatCompletionRequest, ChatCompletionResponse, ImageGenerationApiRequest, ImageGenerationApiResponse, \
    AudioGenerationApiRequest, AudioGenerationApiResponse, AudioTranscriptionApiRequest, AudioTranscriptionApiResponse, \
    ModelMessage
from geenii.provider.interfaces import AICompletionProvider, AIProvider, AIImageGeneratorProvider, \
    AIAudioGeneratorProvider, AIAudioTranscriptionProvider, AIAudioTranslationProvider, AIChatCompletionProvider

type AIProviderType = AICompletionProvider | AIImageGeneratorProvider | AIAudioGeneratorProvider \
                      | AIAudioTranscriptionProvider | AIAudioTranslationProvider | AIProvider


def split_model(model_id: str) -> tuple[str, str]:
    """
    Split the model_id string into provider and model name.
    The model string should be in the format "provider:model_name".

    :param model_id: The model identifier string.
    :return: The provider and model name as a tuple.
    """
    if ":" in model_id:
        parts = model_id.split(":", 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()
    raise ValueError("Invalid model")


def map_model_id(model_id: str) -> tuple[str, str]:
    """
    Map a model ID in the format "provider/model_name" to its provider and model name components.

    :param model_id: The model ID to map.
    :return: A tuple containing the provider name and model name.
    """
    if ":" in model_id:
        parts = model_id.split(":", 1)
        if len(parts) == 2:
            return parts[0].strip(), parts[1].strip()

    raise ValueError(f"Invalid model ID format: {model_id}. Expected 'provider:model_name'.")


def get_ai_provider(provider: str) -> AIProviderType:
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
    provider_module_name = f"geenii.provider.{provider}.provider"
    attr_name = "ai_provider_class"
    try:
        module = __import__(provider_module_name, fromlist=[attr_name])
        provider_class = getattr(module, attr_name, None)
        if provider_class is None:
            raise ImportError(f"No AIProvider subclass found in module {provider_module_name}")
        _ai = provider_class()
    except ImportError as e:
        raise ImportError(f"Could not import provider '{provider}': {str(e)}")

    # check if the provider supports the requested interface
    # the interface is the module name of the provider interface
    #if iface is not None and not isinstance(_ai, iface):
    #    raise RuntimeError(f"Invalid AI: {provider} provider does not support {iface.__name__} interface.")
    return _ai


def get_ai_provider_from_model_id(model_id: str, iface = None) -> tuple[AIProviderType, str, str]:
    """
    Get the AI provider instance based on the model ID.

    :param model_id: The model ID in the format "provider/model_name".
    :return: A tuple containing the AIProvider instance, provider name, and model name.
    """
    provider_name, model_name = map_model_id(model_id)
    ai_provider = get_ai_provider(provider_name)
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


def generate_completion(model: str, prompt: str, stream: bool = False, **kwargs) -> CompletionResponse:
    """
    Generate a completion using the specified AI provider and model.
    """
    response = None
    try:
        #publish_event(["ai.completion.requested"], {"request": request.model_dump()})

        ai, provider, model_name = get_ai_completion_provider(model)

        completion_kwargs = {
            'prompt': prompt,
            'stream': stream,
            'model': model_name, # use only the model name without provider prefix
            **kwargs
        }
        response = ai.generate_completion(**completion_kwargs)

        # Publish the completion response event
        #publish_event(["ai.completion.completed"], {"response": response.model_dump()})
        return response
    except Exception as e:
        print(f"Error in {model} completion API: {str(e)}")

        # Publish the error event
        #publish_event(["ai.completion.error"], {"error": str(e), "request": request.model_dump()})

        return CompletionErrorResponse(error=str(e))
    finally:
        #if response:
        #    print(f"Completion response: {response.model_dump()}")
        #    response.save()
        #    print("Completion response saved.")
        pass


def generate_chat_completion(model: str,
                             prompt: str,
                             system: str = None,
                             messages: list[ModelMessage] = None,
                             tools: list[str] = None,
                             output_format: str = None,
                             output_schema: dict = None,
                             stream: bool = False,
                             **kwargs) -> CompletionResponse:
    """
    Generate an assistant completion using the specified AI provider and model.
    """
    try:
        ai, provider_name, model_name = get_ai_completion_provider(model)
        if not isinstance(ai, AIChatCompletionProvider):
            raise RuntimeError(f"Invalid AI provider: {provider_name} does not support assistant completions.")

        stream = False # Stream is not supported yet, so we force it to False.
        messages = messages or []
        approved_tools = tools or []

        request = ChatCompletionRequest(
            model=model_name,
            system=system,
            prompt=prompt,
            messages=messages,
            tools=approved_tools,
            output_format=output_format,
            stream=stream,
            #model_parameters=kwargs
        )

        response = ai.generate_chat_completion(request)
        return response
    except Exception as e:
        print(f"Error in {model} assistant API: {str(e)}")
        #return ErrorApiResponse(error=str(e))
        raise e


def generate_image(request: ImageGenerationApiRequest) -> ImageGenerationApiResponse | CompletionErrorResponse:
    """
    Generate an image using the specified AI provider and model.
    """
    try:
        # Publish the image generation request event
        #publish_event(["ai.image.generate"], {"request": request.model_dump()})

        ai, provider, model = get_ai_image_generator_provider(request.model)

        args = request.model_dump(exclude={"model"})
        print("Generating image with args:", args)
        response = ai.generate_image(model=model, **args)

        # Publish the image generation response event
        #publish_event(["ai.image.generated"], {"response": response.model_dump()})

        return response
        #return ErrorApiResponse(error="Image generation is not supported yet.")
    except Exception as e:
        # Publish the error event
        #publish_event(["ai.image.generate.error"], {"error": str(e), "request": request.model_dump()})
        return CompletionErrorResponse(error=str(e))


def generate_speech(request: AudioGenerationApiRequest) -> AudioGenerationApiResponse | CompletionErrorResponse:
    """
    Generate speech from text using the specified AI provider and model.
    """
    try:
        ai, provider, model = get_ai_audio_generator_provider(request.model)
        response = ai.generate_speech(model=model,
                                      text=request.text)
        return response
    except Exception as e:
        return CompletionErrorResponse(error=str(e))


def generate_audio_transcription(request: AudioTranscriptionApiRequest) -> AudioTranscriptionApiResponse | CompletionErrorResponse:
    """
    Generate a transcription from audio using the specified AI provider and model.
    """
    try:
        ai, provider, model = get_ai_audio_transcription_provider(request.model)
        response = ai.generate_audio_transcription(model=model,
                                                   audio=request.input_file)
        return response
    except Exception as e:
        return CompletionErrorResponse(error=str(e))

