import os
import shutil
import uuid
import logging

from fastapi import APIRouter, UploadFile, File, HTTPException

from geenii import ai
from geenii.ai import enumerate_models
from geenii.chat.chat_models import TextContent
from geenii.datamodels import CompletionErrorResponse, CompletionRequest, CompletionResponse, ChatCompletionRequest, \
    ChatCompletionResponse, ImageGenerationApiResponse, \
    ImageGenerationApiRequest, AudioGenerationApiRequest, AudioSpeechGenerationApiResponse, AudioTranscriptionApiRequest, \
    AudioTranscriptionApiResponse, AudioTranslationApiResponse, AudioTranslationApiRequest, AIModelInfo, ModelMessage
from geenii.config import DATA_DIR, DEFAULT_AUDIO_TRANSCRIPTION_MODEL
from geenii.memory import FileChatMemory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/models")
async def models() -> list[AIModelInfo]:
    """
    List all available AI models.
    """
    return enumerate_models()


# @router.post("/models/install")
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


@router.post("/chat/completion")
async def chat_completion(request: ChatCompletionRequest) -> ChatCompletionResponse | CompletionErrorResponse:
    """
    Generate a chat completion using the specified AI provider and model.
    """
    context_id = request.context_id or uuid.uuid4().hex
    context_memory_dir = f"{DATA_DIR}/sessions/chat/{context_id}"
    os.makedirs(context_memory_dir, exist_ok=True)

    logger.info(f"Chat completion request with context_id={context_id}, model={request.model}, prompt={request.prompt}")
    memory = FileChatMemory(f"{context_memory_dir}/memory.jsonl", create=True, restore=True)

    messages = list(memory.messages)
    logger.info(f"Loaded {len(messages)} messages from memory for context_id={context_id}")
    if len(messages) > 10:
        logger.warning(f"Memory for context_id={context_id} has {len(messages)} messages, which may exceed token limits for some models. Consider implementing memory management strategies.")
        # todo compact memory

    system = ["You are a helpful assistant that helps the user with their tasks. Give short and concise answers. Always try to help the user as best as you can. If you don't know the answer, say you don't know and don't try to make up an answer."]

    try:
        _request = ChatCompletionRequest(
            system=system,
            model=request.model,
            prompt=request.prompt,
            messages=messages,
            context_id=context_id,
        )
        response = ai.generate_chat_completion(request=_request)

        # Append the user message and assistant response to memory
        memory.append(ModelMessage(role="user", content=[TextContent(type="text", text=request.prompt)]))
        memory.append(ModelMessage(role="assistant", content=response.output))

        return response
    except Exception as e:
        logger.error(f"Error during chat completion for context_id={context_id}: {e}")
        return CompletionErrorResponse(error=str(e))


### IMAGE GENERATION
@router.post("/image/generate")
async def generate_image(request: ImageGenerationApiRequest) -> ImageGenerationApiResponse | CompletionErrorResponse:
    """
    Generate an image using the specified AI provider and model.
    """
    return ai.generate_image(request)


# AUDIO GENERATION - TEXT-TO-SPEECH
@router.post("/audio/speech")
async def generate_speech(request: AudioGenerationApiRequest) -> AudioSpeechGenerationApiResponse | CompletionErrorResponse:
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