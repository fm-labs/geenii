from fastapi import APIRouter

from geenii.datamodels import ErrorApiResponse, CompletionApiRequest, CompletionApiResponse, AssistantApiRequest, \
    AssistantApiResponse, ImageGenerationApiResponse, \
    ImageGenerationApiRequest, AudioGenerationApiRequest, AudioGenerationApiResponse, AudioTranscriptionApiRequest, \
    AudioTranscriptionApiResponse, AudioTranslationApiResponse, AudioTranslationApiRequest
import geenii.service as ai_service

router = APIRouter(prefix="/ai/v1", tags=["ai"])


@router.get("/models")
async def models() -> list[dict]:
    """
    List all available AI models.
    """
    return [
        {
            "name": "gpt-3.5-turbo",
            "provider": "openai",
            "type": "text-completion",
            "description": "OpenAI's GPT-3.5 Turbo model for text completion tasks."
        },
        {
            "name": "dall-e-2",
            "provider": "openai",
            "type": "image-generation",
            "description": "OpenAI's DALL-E 2 model for generating images from text prompts."
        },
        {
            "name": "whisper-large-v3",
            "provider": "openai",
            "type": "audio-transcription",
            "description": "OpenAI's Whisper Large v3 model for transcribing audio to text."
        }
    ]


@router.post("/completion")
async def completion(request: CompletionApiRequest) -> CompletionApiResponse | ErrorApiResponse:
    """
    Generate a completion using the specified AI provider and model.
    """
    return ai_service.generate_completion(request)


# @router.post("/assistant", response_model=AssistantApiResponse)
# async def assistant(request: AssistantApiRequest) -> AssistantApiResponse:
#     """
#     Generate an assistant completion using the specified AI provider and model.
#     """
#     return ai_service.generate_assistant_completion(request)


### IMAGE GENERATION
@router.post("/image/generate")
async def generate_image(request: ImageGenerationApiRequest) -> ImageGenerationApiResponse | ErrorApiResponse:
    """
    Generate an image using the specified AI provider and model.
    """
    return ai_service.generate_image(request)


# AUDIO GENERATION - TEXT-TO-SPEECH
@router.post("/audio/speech")
async def generate_speech(request: AudioGenerationApiRequest) -> AudioGenerationApiResponse | ErrorApiResponse:
    """
    Generate speech from text using the specified AI provider and model.
    """
    return ai_service.generate_speech(request)


# AUDIO TRANSCRIPTION - SPEECH-TO-TEXT
@router.post("/audio/transcribe")
async def generate_audio_transcription(request: AudioTranscriptionApiRequest) -> AudioTranscriptionApiResponse | ErrorApiResponse:
    """
    Generate a transcription from audio using the specified AI provider and model.
    """
    return ai_service.generate_audio_transcription(request)


# AUDIO TRANSCRIPTION - SPEECH-TO-TEXT
@router.post("/audio/translate")
async def generate_audio_transcription(request: AudioTranslationApiRequest) -> AudioTranslationApiResponse | ErrorApiResponse:
    """
    Generate a transcription from audio using the specified AI provider and model.
    """
    #return ai_service.generate_audio_translation(request)
    raise NotImplementedError("Audio translation is not implemented yet.")