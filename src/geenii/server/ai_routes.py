import logging
import os
import re
import uuid
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, HTTPException

from geenii import ai
from geenii.ai import enumerate_models
from geenii.chat_models import TextContent
from geenii.config import DEFAULT_AUDIO_TRANSCRIPTION_MODEL, GEENII_CHAT_SESSIONS_DIR
from geenii.datamodels import CompletionErrorResponse, CompletionRequest, CompletionResponse, ChatCompletionRequest, \
    ChatCompletionResponse, ImageGenerationApiResponse, \
    ImageGenerationApiRequest, AudioGenerationApiRequest, AudioSpeechGenerationApiResponse, \
    AudioTranscriptionApiRequest, \
    AudioTranscriptionApiResponse, AudioTranslationApiResponse, AudioTranslationApiRequest, AIModelInfo, ModelMessage, \
    Problem
from geenii.memory import FileChatMemory
from geenii.utils.os_util import get_user_home_dir

logger = logging.getLogger(__name__)

# Errors are returned as real HTTP status codes with a Problem body (see the HTTPException handler in server.py):
# 400 for invalid input, 502 when the AI provider fails, 501 for endpoints that are not implemented yet.
_ERROR_RESPONSES = {
    400: {"model": Problem, "description": "Invalid request"},
    502: {"model": Problem, "description": "AI provider error"},
}

router = APIRouter(prefix="/ai", tags=["ai"], responses=_ERROR_RESPONSES)

# Handlers are plain `def` on purpose: the ai.* calls block (provider HTTP, file I/O),
# so FastAPI runs them in its threadpool instead of on the event loop.

_CONTEXT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")

DEFAULT_CHAT_SYSTEM_PROMPT = "You are a helpful assistant that helps the user with their tasks. Give short and concise answers. Always try to help the user as best as you can. If you don't know the answer, say you don't know and don't try to make up an answer."

AUDIO_UPLOAD_DIR = Path(get_user_home_dir()) / ".geenii" / "uploads" / "audio"
MAX_AUDIO_UPLOAD_BYTES = 25 * 1024 * 1024
_AUDIO_EXT_RE = re.compile(r"^\.[A-Za-z0-9]{1,8}$")
_UPLOAD_CHUNK_SIZE = 1024 * 1024


def _chat_session_dir(context_id: str) -> Path:
    """Resolve the session directory for a client-supplied context_id, rejecting anything that could escape it."""
    if not _CONTEXT_ID_RE.fullmatch(context_id):
        raise HTTPException(status_code=400, detail="Invalid context_id: expected 1-64 characters of [A-Za-z0-9_-].")
    base = GEENII_CHAT_SESSIONS_DIR.resolve()
    path = (base / context_id).resolve()
    if path.parent != base:
        raise HTTPException(status_code=400, detail="Invalid context_id.")
    return path


def _check_model_id(model: str | None):
    """Reject malformed 'provider:model' IDs as a client error before calling the provider."""
    if not model:
        return
    try:
        ai.split_model_id(model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _unwrap(result):
    """ai.* helpers report most provider failures as a CompletionErrorResponse; turn those into a 502."""
    if isinstance(result, CompletionErrorResponse):
        raise HTTPException(status_code=502, detail=result.error)
    return result


def _model_kwargs(request: CompletionRequest) -> dict:
    """Generation parameters to forward to the provider. None values are dropped so provider defaults apply."""
    kwargs = request.model_dump(include={"system", "temperature", "top_p", "max_tokens", "output_format",
                                         "output_schema", "model_parameters"})
    return {k: v for k, v in kwargs.items() if v is not None and v != {}}


@router.get("/models")
def models() -> list[AIModelInfo]:
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
def completion(request: CompletionRequest) -> CompletionResponse:
    """
    Generate a completion using the specified AI provider and model.

    Streaming is not supported by this endpoint; `stream` is ignored.
    """
    _check_model_id(request.model)
    return _unwrap(ai.generate_completion(
        model=request.model,
        prompt=request.prompt,
        stream=False,
        source="api",
        task="completion",
        **_model_kwargs(request),
    ))


@router.post("/chat/completion")
def chat_completion(request: ChatCompletionRequest) -> ChatCompletionResponse:
    """
    Generate a chat completion using the specified AI provider and model.

    The conversation history is kept server-side per `context_id`; client-supplied `messages` are ignored.
    `tools` are not supported here (tool execution belongs to the agents) and are ignored as well.
    """
    _check_model_id(request.model)
    context_id = request.context_id or uuid.uuid4().hex
    context_memory_dir = _chat_session_dir(context_id)
    context_memory_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Chat completion request with context_id={context_id}, model={request.model}, prompt={request.prompt}")
    memory = FileChatMemory(f"{context_memory_dir}/memory.jsonl", create=True, restore=True)

    messages = list(memory.messages)
    logger.info(f"Loaded {len(messages)} messages from memory for context_id={context_id}")
    if len(messages) > 10:
        logger.warning(f"Memory for context_id={context_id} has {len(messages)} messages, which may exceed token limits for some models. Consider implementing memory management strategies.")
        # todo compact memory

    _request = ChatCompletionRequest(
        **_model_kwargs(request),
        model=request.model,
        prompt=request.prompt,
        messages=messages,
        context_id=context_id,
    )
    if not _request.system:
        _request.system = [DEFAULT_CHAT_SYSTEM_PROMPT]

    try:
        response = ai.generate_chat_completion(request=_request, source="api", task="chat_completion")
    except Exception as e:
        logger.error(f"Error during chat completion for context_id={context_id}: {e}")
        raise HTTPException(status_code=502, detail=str(e))

    # Append the user message and assistant response to memory
    memory.append(ModelMessage(role="user", content=[TextContent(type="text", text=request.prompt)]))
    memory.append(ModelMessage(role="assistant", content=response.output))

    return response


### IMAGE GENERATION
@router.post("/image/generate")
def generate_image(request: ImageGenerationApiRequest) -> ImageGenerationApiResponse:
    """
    Generate an image using the specified AI provider and model.
    """
    _check_model_id(request.model)
    return _unwrap(ai.generate_image(request))


# AUDIO GENERATION - TEXT-TO-SPEECH
@router.post("/audio/speech")
def generate_speech(request: AudioGenerationApiRequest) -> AudioSpeechGenerationApiResponse:
    """
    Generate speech from text using the specified AI provider and model.
    """
    _check_model_id(request.model)
    return _unwrap(ai.generate_speech(request))


def _save_upload(file: UploadFile, max_bytes: int) -> Path:
    """Stream an upload to AUDIO_UPLOAD_DIR under a random name, aborting with 413 once it exceeds max_bytes."""
    AUDIO_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

    # don't trust the client filename; keep only a plain extension
    ext = os.path.splitext(file.filename or "")[1]
    if not _AUDIO_EXT_RE.fullmatch(ext):
        ext = ".bin"
    save_path = AUDIO_UPLOAD_DIR / f"{uuid.uuid4().hex}{ext}"

    size = 0
    try:
        with open(save_path, "wb") as out:
            # UploadFile.file is a SpooledTemporaryFile; copy in chunks without loading it into memory
            while chunk := file.file.read(_UPLOAD_CHUNK_SIZE):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=413,
                                        detail=f"Audio file too large (max {max_bytes // (1024 * 1024)} MB).")
                out.write(chunk)
    except BaseException:
        save_path.unlink(missing_ok=True)
        raise
    return save_path


# AUDIO TRANSCRIPTION - SPEECH-TO-TEXT
@router.post("/audio/transcribe", responses={413: {"model": Problem, "description": "Audio file too large"}})
def generate_audio_transcription(input_blob: UploadFile = File(...)) -> AudioTranscriptionApiResponse:
    """
    Generate a transcription from audio using the specified AI provider and model.

    The uploaded file is only kept for the duration of the request.
    """
    file = input_blob
    if not file.content_type or not file.content_type.startswith("audio/"):
        raise HTTPException(status_code=400, detail=f"Expected audio/*, got {file.content_type}")

    save_path = _save_upload(file, MAX_AUDIO_UPLOAD_BYTES)
    try:
        return _unwrap(ai.generate_audio_transcription(AudioTranscriptionApiRequest(
            model=DEFAULT_AUDIO_TRANSCRIPTION_MODEL,
            input_file=str(save_path),
        )))
    finally:
        save_path.unlink(missing_ok=True)


# AUDIO TRANSLATION - SPEECH-TO-TEXT (TRANSLATED)
@router.post("/audio/translate", responses={501: {"model": Problem, "description": "Not implemented"}})
def generate_audio_translation(request: AudioTranslationApiRequest) -> AudioTranslationApiResponse:
    """
    Translate audio into text in the target language. Not implemented yet.
    """
    #return ai_service.generate_audio_translation(request)
    raise HTTPException(status_code=501, detail="Audio translation is not implemented yet.")
