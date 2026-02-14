import os
import shutil
import uuid

from fastapi import APIRouter, UploadFile, File, HTTPException

from geenii import ai
from geenii.datamodels import CompletionErrorResponse, CompletionRequest, CompletionResponse, ChatCompletionRequest, \
    ChatCompletionResponse, ImageGenerationApiResponse, \
    ImageGenerationApiRequest, AudioGenerationApiRequest, AudioGenerationApiResponse, AudioTranscriptionApiRequest, \
    AudioTranscriptionApiResponse, AudioTranslationApiResponse, AudioTranslationApiRequest
from geenii.settings import DATA_DIR, DEFAULT_AUDIO_TRANSCRIPTION_MODEL

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

# @router.post("/models/download")
# async def download_model(provider_name: str, model_name: str) -> dict:
#     """
#     Download the specified AI model for local use.
#     """
#     #result = ai_service.download_model(model_name)
#     #return {"status": "success" if result else "failure", "model": model_name}
#     raise NotImplementedError("Model downloading is not implemented yet.")



@router.post("/completion")
async def completion(request: CompletionRequest) -> CompletionResponse | CompletionErrorResponse:
    """
    Generate a completion using the specified AI provider and model.
    """
    return ai.generate_completion(
        model=request.model,
        prompt=request.prompt,
    )


# @router.post("/assistant", response_model=AssistantApiResponse)
# async def assistant(request: AssistantApiRequest) -> AssistantApiResponse:
#     """
#     Generate an assistant completion using the specified AI provider and model.
#     """
#     return ai_service.generate_assistant_completion(request)


### IMAGE GENERATION
@router.post("/image/generate")
async def generate_image(request: ImageGenerationApiRequest) -> ImageGenerationApiResponse | CompletionErrorResponse:
    """
    Generate an image using the specified AI provider and model.
    """
    return ai.generate_image(request)


# AUDIO GENERATION - TEXT-TO-SPEECH
@router.post("/audio/speech")
async def generate_speech(request: AudioGenerationApiRequest) -> AudioGenerationApiResponse | CompletionErrorResponse:
    """
    Generate speech from text using the specified AI provider and model.
    """
    return ai.generate_speech(request)


# AUDIO TRANSCRIPTION - SPEECH-TO-TEXT
@router.post("/audio/transcribe")
async def generate_audio_transcription(input_blob: UploadFile = File(...)) -> AudioTranscriptionApiResponse | CompletionErrorResponse:
    """
    Generate a transcription from audio using the specified AI provider and model.
    """
    UPLOAD_DIR = f"{DATA_DIR}/uploads/audio"
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    file = input_blob
    # Basic validation (optional but recommended)
    if not file.content_type or not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail=f"Expected audio/*, got {file.content_type}")

    # Choose a filename (don’t trust client filename)
    ext = os.path.splitext(file.filename or "")[1] or ".bin"
    safe_name = f"{uuid.uuid4().hex}{ext}"
    save_path = os.path.join(UPLOAD_DIR, safe_name)

    # Save without loading the whole file into memory
    # UploadFile.file is a SpooledTemporaryFile (file-like)
    with open(save_path, "wb") as out:
        shutil.copyfileobj(file.file, out)

    print(f"File saved: {save_path}")
    return ai.generate_audio_transcription(AudioTranscriptionApiRequest(
        model=DEFAULT_AUDIO_TRANSCRIPTION_MODEL,
        input_file=save_path,
    ))


# AUDIO TRANSCRIPTION - SPEECH-TO-TEXT
@router.post("/audio/translate")
async def generate_audio_transcription(request: AudioTranslationApiRequest) -> AudioTranslationApiResponse | CompletionErrorResponse:
    """
    Generate a transcription from audio using the specified AI provider and model.
    """
    #return ai_service.generate_audio_translation(request)
    raise NotImplementedError("Audio translation is not implemented yet.")