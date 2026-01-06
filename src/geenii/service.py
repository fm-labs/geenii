from geenii.ai import get_ai_completion_provider, get_ai_image_generator_provider, \
    get_ai_audio_generator_provider, get_ai_audio_transcription_provider
from geenii.datamodels import ErrorApiResponse, CompletionApiRequest, CompletionApiResponse, AssistantApiRequest, \
    AssistantApiResponse, ImageGenerationApiResponse, \
    ImageGenerationApiRequest, AudioGenerationApiRequest, AudioGenerationApiResponse, AudioTranscriptionApiRequest, \
    AudioTranscriptionApiResponse
from geenii.server.routes.route_pubsub import publish_event


def generate_completion(request: CompletionApiRequest) -> CompletionApiResponse | ErrorApiResponse:
    """
    Generate a completion using the specified AI provider and model.
    """
    try:
        #publish_event(["ai.completion.created"], {"request": request.model_dump()})

        stream = False # request.stream # Stream is not supported yet, so we ignore it for now.

        ai, provider, model = get_ai_completion_provider(request.model)
        response = ai.generate_completion(prompt=request.prompt,
                                          model=model,
                                          stream=stream)

        # Publish the completion response event
        #publish_event(["ai.completion.completed"], {"response": response.model_dump()})
        return response
    except Exception as e:
        print(f"Error in {request.model} completion API: {str(e)}")

        # Publish the error event
        #publish_event(["ai.completion.error"], {"error": str(e), "request": request.model_dump()})

        return ErrorApiResponse(error=str(e))


def generate_assistant_completion(request: AssistantApiRequest) -> AssistantApiResponse:
    """
    Generate an assistant completion using the specified AI provider and model.
    """
    try:
        stream = False # request.stream # Stream is not supported yet, so we ignore it for now.

        ai, provider, model = get_ai_completion_provider(request.model)

        requested_tools = request.tools or []
        response = ai.generate_assistant_completion(model=model,
                                                    prompt=request.prompt,
                                                    tool_names=requested_tools,
                                                    stream=stream)
        return response
    except Exception as e:
        print(f"Error in {request.model} assistant API: {str(e)}")
        #return ErrorApiResponse(error=str(e))
        raise e


### IMAGE GENERATION
def generate_image(request: ImageGenerationApiRequest) -> ImageGenerationApiResponse | ErrorApiResponse:
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
        return ErrorApiResponse(error=str(e))


# AUDIO GENERATION - TEXT-TO-SPEECH
def generate_speech(request: AudioGenerationApiRequest) -> AudioGenerationApiResponse | ErrorApiResponse:
    """
    Generate speech from text using the specified AI provider and model.
    """
    try:
        ai, provider, model = get_ai_audio_generator_provider(request.model)
        response = ai.generate_speech(model=model,
                                      text=request.text)
        return response
    except Exception as e:
        return ErrorApiResponse(error=str(e))


# AUDIO TRANSCRIPTION - SPEECH-TO-TEXT
def generate_audio_transcription(request: AudioTranscriptionApiRequest) -> AudioTranscriptionApiResponse | ErrorApiResponse:
    """
    Generate a transcription from audio using the specified AI provider and model.
    """
    try:
        ai, provider, model = get_ai_audio_transcription_provider(request.model)
        response = ai.generate_audio_transcription(model=model,
                                                   audio=request.input_file)
        return response
    except Exception as e:
        return ErrorApiResponse(error=str(e))