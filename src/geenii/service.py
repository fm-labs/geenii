from geenii.ai import get_ai_completion_provider, get_ai_image_generator_provider, \
    get_ai_audio_generator_provider, get_ai_audio_transcription_provider
from geenii.datamodels import CompletionErrorResponse, CompletionRequest, CompletionResponse, AssistantCompletionRequest, \
    AssistantCompletionResponse, ImageGenerationApiResponse, \
    ImageGenerationApiRequest, AudioGenerationApiRequest, AudioGenerationApiResponse, AudioTranscriptionApiRequest, \
    AudioTranscriptionApiResponse
from geenii.server.routes.route_pubsub import publish_event


def generate_completion(request: CompletionRequest) -> CompletionResponse | CompletionErrorResponse:
    """
    Generate a completion using the specified AI provider and model.
    """
    response = None
    try:
        #publish_event(["ai.completion.requested"], {"request": request.model_dump()})

        ai, provider, model_name = get_ai_completion_provider(request.model)

        request.stream = False # Stream is not supported yet, so we force it to False.
        completion_kwargs = request.model_dump()
        completion_kwargs['model'] = model_name # use only the model name without provider prefix
        response = ai.generate_completion(**completion_kwargs)

        # Publish the completion response event
        #publish_event(["ai.completion.completed"], {"response": response.model_dump()})
        return response
    except Exception as e:
        print(f"Error in {request.model} completion API: {str(e)}")

        # Publish the error event
        #publish_event(["ai.completion.error"], {"error": str(e), "request": request.model_dump()})

        return CompletionErrorResponse(error=str(e))
    finally:
        if response:
            print(f"Completion response: {response.model_dump()}")
            response.save()
            print("Completion response saved.")



def generate_assistant_completion(request: AssistantCompletionRequest) -> AssistantCompletionResponse:
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


# AUDIO GENERATION - TEXT-TO-SPEECH
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


# AUDIO TRANSCRIPTION - SPEECH-TO-TEXT
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