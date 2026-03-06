import json
import os
import uuid
import logging

from fastapi import APIRouter
from fastapi.params import Depends

from geenii import ai
from geenii.chat.chat_manager import ChatManager
from geenii.chat.chat_models import TextContent
from geenii.chat.chat_server_routes import dep_chat_mgr
from geenii.config import DATA_DIR
from geenii.datamodels import ChatCompletionRequest, ChatCompletionResponse, CompletionErrorResponse, ModelMessage
from geenii.memory import FileChatMemory
from geenii.server.deps import dep_current_user, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])

def read_agents_from_file():
    fp = f"{DATA_DIR}/agents.json"
    if os.path.exists(fp):
        try:
            with open(fp, "r") as f:
                agents = json.load(f)
                return agents
        except Exception as e:
            print(f"Error reading agents from file: {e}")
            return []
    else:
        print(f"Error reading agents from file: {fp}")
        return []


@router.get("/")
def list_agents():
    """
    List all available agents.
    """
    agents = read_agents_from_file()
    return {"agents": agents}


@router.get("/{agent_name}/chat")
def get_agent_chat_room(agent_name: str, chat_mgr: ChatManager = Depends(dep_chat_mgr), user: User = Depends(dep_current_user)):
    """
    Get or create a chat room for the specified agent.
    """
    owner = user.username
    room = chat_mgr.get_dm_room(owner=owner, peer="geenii:bot:"+agent_name, auto_create=True, auto_join=True)
    room_id = room.id
    return {"room_id": room_id}


@router.post("/completion")
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


@router.post("/callback")
def agent_callback(data: dict):
    """
    Endpoint for agents to send callbacks with results or status updates.
    """
    print("Received agent callback:", data)
    interaction_type = data.get("interaction_type")
    interaction_id = data.get("interaction_id")
    if not interaction_type or not interaction_id:
        return {"status": "error", "message": "Missing 'type' or 'id' in callback data."}

    # Handle different types of interactions
    if interaction_type == "tool_call_request":
        # -> tool_call_request
        # check if any file tickets need to be resolved for this interaction
        # rename to .approved to signal approval or .rejected to signal rejection
        choice = data.get("choice")
        ticket_file = f"{DATA_DIR}/cache/hidl/{interaction_id}.json"
        approved_file = f"{DATA_DIR}/cache/hidl/{interaction_id}.approved"
        rejected_file = f"{DATA_DIR}/cache/hidl/{interaction_id}.rejected"
        if os.path.exists(ticket_file):
            if choice and choice.lower() == "allow":
                os.rename(ticket_file, approved_file)
                return {"status": "approved"}
            else:
                os.rename(ticket_file, rejected_file)
                return {"status": "rejected"}

    return {"status": "noop"}