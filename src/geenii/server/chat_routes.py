import logging
import threading
from collections.abc import Iterator

import pydantic
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse

from geenii.chat_models import ContentPart, TextContent
from geenii.config import GEENII_CHAT_SESSIONS_DIR
from geenii.datamodels import ChatMessage, ChatStreamEvent, Problem
from geenii.server.chat_sessions import (
    ChatSessionInfo,
    ChatSessionNotFound,
    ChatSessionStore,
)
from geenii.server.web_runner import AgentBusyError

logger = logging.getLogger(__name__)

# Agent chat sessions for the xchat UI. (The plain completion chat lives in ai_routes.)
#
# Flow: POST /chats -> session id; POST /chats/{id}/messages streams the agent's turn as NDJSON ChatStreamEvents.
# Tool approval requests arrive as messages with an `interaction` part; answer them with
# POST /chats/{id}/interactions/{interaction_id} while the stream is open.
#
# Handlers are plain `def`: agents block (provider HTTP, tools), so they run in FastAPI's threadpool.

router = APIRouter(
    prefix="/chats",
    tags=["chat"],
    responses={
        400: {"model": Problem, "description": "Invalid request"},
        404: {"model": Problem, "description": "Chat not found"},
    },
)

NDJSON_MEDIA_TYPE = "application/x-ndjson"

_store_lock = threading.Lock()


def dep_chat_sessions(request: Request) -> ChatSessionStore:
    store = getattr(request.app.state, "chat_sessions", None)
    if store is None:
        with _store_lock:
            store = getattr(request.app.state, "chat_sessions", None)
            if store is None:
                store = ChatSessionStore(GEENII_CHAT_SESSIONS_DIR, request.app.state.agent_registry)
                request.app.state.chat_sessions = store
    return store


def _get(store: ChatSessionStore, context_id: str) -> ChatSessionInfo:
    try:
        return store.get(context_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ChatSessionNotFound:
        raise HTTPException(status_code=404, detail=f"Chat {context_id} not found.")


class ChatCreateRequest(pydantic.BaseModel):
    agent: str = "default"
    title: str | None = None


class ChatPostMessageRequest(pydantic.BaseModel):
    prompt: str | None = None
    content: list[ContentPart] | None = None

    @pydantic.model_validator(mode="after")
    def _require_input(self):
        if not (self.prompt and self.prompt.strip()) and not self.content:
            raise ValueError("Either 'prompt' or 'content' is required.")
        return self

    def agent_input(self) -> str | list[ContentPart]:
        """The agent's macros (/command, @agent, :tool) only apply to plain text, so text-only input is passed as str."""
        if self.content:
            if len(self.content) == 1 and isinstance(self.content[0], TextContent):
                return self.content[0].text
            return self.content
        return self.prompt

    def prompt_text(self) -> str:
        if self.content:
            return " ".join(p.text for p in self.content if isinstance(p, TextContent))
        return self.prompt or ""


class ChatInteractionResponse(pydantic.BaseModel):
    choice: str


@router.get("")
def list_chats(
    store: ChatSessionStore = Depends(dep_chat_sessions),
) -> list[ChatSessionInfo]:
    """List agent chat sessions, most recently updated first."""
    return store.list()


@router.post("", status_code=201)
def create_chat(request: ChatCreateRequest, store: ChatSessionStore = Depends(dep_chat_sessions)) -> ChatSessionInfo:
    """Create a chat session with the given agent."""
    try:
        return store.create(request.agent, title=request.title)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{context_id}")
def get_chat(context_id: str, store: ChatSessionStore = Depends(dep_chat_sessions)) -> ChatSessionInfo:
    return _get(store, context_id)


@router.delete("/{context_id}", status_code=204)
def delete_chat(context_id: str, store: ChatSessionStore = Depends(dep_chat_sessions)):
    """Delete a chat session and its memory. A running turn is cancelled."""
    _get(store, context_id)
    store.delete(context_id)
    return Response(status_code=204)


@router.get("/{context_id}/messages")
def get_chat_messages(context_id: str, store: ChatSessionStore = Depends(dep_chat_sessions)) -> list[ChatMessage]:
    """The conversation history (the agent's memory)."""
    info = _get(store, context_id)
    return [
        ChatMessage(
            id=m.id,
            timestamp=m.timestamp,
            context_id=context_id,
            message=m,
            sender_id="user" if m.role == "user" else info.agent,
        )
        for m in store.history(context_id)
    ]


def _ndjson(events: Iterator[ChatStreamEvent]) -> Iterator[str]:
    for event in events:
        yield event.model_dump_json() + "\n"


@router.post(
    "/{context_id}/messages",
    responses={
        200: {
            "description": "NDJSON stream of ChatStreamEvent objects, one per line",
            "content": {NDJSON_MEDIA_TYPE: {}},
        },
        409: {
            "model": Problem,
            "description": "A turn is already running in this chat",
        },
    },
)
def post_chat_message(
    context_id: str,
    request: ChatPostMessageRequest,
    store: ChatSessionStore = Depends(dep_chat_sessions),
):
    """
    Send a message to the chat's agent and stream its turn as NDJSON `ChatStreamEvent`s
    (`message`, `status`, `error`, terminated by `done`).
    """
    _get(store, context_id)
    try:
        events = store.runner(context_id).start(request.agent_input())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except AgentBusyError as e:
        raise HTTPException(status_code=409, detail=str(e))

    store.touch(context_id, prompt=request.prompt_text())
    return StreamingResponse(_ndjson(events), media_type=NDJSON_MEDIA_TYPE)


@router.post("/{context_id}/interactions/{interaction_id}", status_code=204)
def respond_to_interaction(
    context_id: str,
    interaction_id: str,
    response: ChatInteractionResponse,
    store: ChatSessionStore = Depends(dep_chat_sessions),
):
    """Answer an approval request of the running turn (e.g. choice "Allow" or "Deny")."""
    _get(store, context_id)
    runner = store.get_runner(context_id)
    if not runner or not runner.respond(interaction_id, response.choice):
        raise HTTPException(status_code=404, detail=f"No pending interaction {interaction_id}.")
    return Response(status_code=204)


@router.post("/{context_id}/cancel", status_code=204)
def cancel_chat_turn(context_id: str, store: ChatSessionStore = Depends(dep_chat_sessions)):
    """Cancel the running turn: pending approvals are rejected and the stream ends at the next message."""
    _get(store, context_id)
    runner = store.get_runner(context_id)
    if runner:
        runner.cancel()
    return Response(status_code=204)


_NOT_IMPLEMENTED = {501: {"model": Problem, "description": "Not implemented"}}


@router.post("/{context_id}/files", responses=_NOT_IMPLEMENTED)
def upload_files(context_id: str):
    raise HTTPException(status_code=501, detail="Chat file uploads are not implemented yet.")


@router.get("/{context_id}/files", responses=_NOT_IMPLEMENTED)
def list_files(context_id: str):
    raise HTTPException(status_code=501, detail="Chat files are not implemented yet.")


@router.get("/{context_id}/files/{filename}", responses=_NOT_IMPLEMENTED)
def read_file(context_id: str, filename: str):
    raise HTTPException(status_code=501, detail="Chat files are not implemented yet.")
