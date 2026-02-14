import uuid
import json
import os
from typing import List

import pydantic
from anthropic.types import ErrorResponse
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ConfigDict
from starlette import status

from geenii.chat.memory import ChatMemory, FileChatMemory
from geenii.chat.models import ChatConversation, ChatMessageContent, ChatMessage
from geenii.datamodels import CompletionResponse, CompletionErrorResponse
from geenii.server.deps import dep_current_user
from geenii.settings import DATA_DIR
from geenii.wizard.default import DefaultWizard

router = APIRouter(prefix="/ai/v1/assistants", tags=["assistants"])

def get_chat_memory(username: str, assistant_name: str, conversation_id: str, create=False) -> ChatMemory:
    # using a file based chat memory for simplicity
    file_path = f"{DATA_DIR}/chats/{username}/{assistant_name}/{conversation_id}/memory.json"
    print(f"Loading chat memory from {file_path}", create)
    return FileChatMemory(file_path, create=create)


def find_conversations_for_user_in_dir(username: str, assistant_name: str) -> list[str]:
    base_path = f"{DATA_DIR}/chats/{username}/{assistant_name}/"
    # subfolders are conversation IDs
    if not os.path.exists(base_path):
        return []
    return [name for name in os.listdir(base_path)
            if os.path.isdir(os.path.join(base_path, name))]


def fetch_assistant_configs_for_user(username: str) -> list[dict]:
    #assistants_json_file = f"{DATA_DIR}/users/{username}/assistants.json"
    assistants_json_file = f"{DATA_DIR}/assistants.json"
    import os
    if not os.path.exists(assistants_json_file):
        return []
    with open(assistants_json_file, 'r') as f:
        data = json.load(f)
        return data

def fetch_assistant_config_by_id_for_user(username: str, assistant_id: str) -> dict | None:
    assistants = fetch_assistant_configs_for_user(username)
    for assistant in assistants:
        if assistant["id"] == assistant_id:
            return assistant
    return None

def update_assistant_config_for_user(username: str, assistant_config: dict) -> None:
    assistants_json_file = f"{DATA_DIR}/assistants.json"
    import os
    assistants = []
    if os.path.exists(assistants_json_file):
        with open(assistants_json_file, 'r') as f:
            assistants = json.load(f)
    # find and update the assistant config
    for i, assistant in enumerate(assistants):
        if assistant["id"] == assistant_config["id"]:
            assistants[i] = assistant_config
            break
    else:
        assistants.append(assistant_config)
    with open(assistants_json_file, 'w') as f:
        json.dump(assistants, f, indent=4)


def init_assistant_for_user(username: str, assistant_id: str, conversation_id: str, create=False) -> DefaultWizard:
    memory = get_chat_memory(username, assistant_id, conversation_id, create=create)
    assistant_config = fetch_assistant_config_by_id_for_user(username, assistant_id)
    if assistant_config is None:
        raise FileNotFoundError("Assistant configuration not found")
    print(f"Initializing assistant {assistant_id}", assistant_config)
    assistant = DefaultWizard(memory=memory, context_id=conversation_id, **(assistant_config or {}))
    return assistant



class AssistantChatInputRequest(pydantic.BaseModel):
    model_config = ConfigDict(extra="allow")

    input: str


class AssistantConfigRequestBody(pydantic.BaseModel):
    model_config = ConfigDict(extra="allow") # todo remove extra allow once implemented

    name: str
    description: str | None = None
    model: str | None = None
    model_parameters: dict | None = None
    system_prompt: str | None = None


class AssistantConfig(AssistantConfigRequestBody):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    description: str | None = None
    model: str | None = None
    model_parameters: dict | None = pydantic.Field(default_factory=dict)
    system_prompt: str | None = None



@router.get("/")
async def list_available_assistants(user = Depends(dep_current_user)) -> List[AssistantConfig]:
    """
    List all available assistantic AI assistants.
    """
    assistant_configs_dict = fetch_assistant_configs_for_user(user["username"])
    return [AssistantConfig(**assistant) for assistant in assistant_configs_dict]


@router.post("/")
def create_assistant(assistant_config: AssistantConfigRequestBody, user = Depends(dep_current_user)) -> AssistantConfig:
    # create a new assistant config and save it
    new_assistant = AssistantConfig(
        id=str(uuid.uuid4().hex),
        name=assistant_config.name,
        description=assistant_config.description,
        model=assistant_config.model,
        model_parameters=assistant_config.model_parameters or {},
        system_prompt=assistant_config.system_prompt
    )
    print("Creating new assistant:", new_assistant)
    update_assistant_config_for_user(user["username"], new_assistant.model_dump())
    return new_assistant


@router.post("/{assistant_id}")
def configure_assistant(assistant_id: str, assistant_config: AssistantConfigRequestBody, user = Depends(dep_current_user)) -> AssistantConfig:
    assistant_dict = fetch_assistant_config_by_id_for_user(user["username"], assistant_id)
    if not assistant_dict:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Assistant not found")
    # update the assistant config
    updated_assistant_config = AssistantConfig(**assistant_dict).model_copy(update=assistant_config.model_dump())
    print("Updating assistant:", updated_assistant_config)
    update_assistant_config_for_user(user["username"], updated_assistant_config.model_dump())
    return updated_assistant_config


@router.get("/{assistant_id}/chats", response_model=List[ChatConversation])
def list_conversations(assistant_id: str, user = Depends(dep_current_user)):
    ids = find_conversations_for_user_in_dir(user["username"], assistant_id)
    conversations = []
    for conv_id in ids:
        conversations.append(ChatConversation(id=conv_id))
    return conversations


@router.post("/{assistant_id}/chats", response_model=ChatConversation)
def create_conversation(assistant_id: str, input: AssistantChatInputRequest, user = Depends(dep_current_user)):
    try:
        conversion_id = str(uuid.uuid4().hex)
        conv = ChatConversation(id=conversion_id, messages=[])

        # get the default assistant for the user
        _assistant = init_assistant_for_user(user["username"], assistant_id, conversion_id, create=True)
        # create a new conversation with the user input as the first message
        assistant_response = _assistant.prompt(input.input)
        # handle error response
        if isinstance(assistant_response, CompletionErrorResponse):
            conv.add_message(ChatMessage(role="system", content=[ChatMessageContent(type="text", text=f"Error: {assistant_response.error_message}")]))
        elif isinstance(assistant_response, CompletionResponse):
            conv.add_message(ChatMessage(role="user", content=[ChatMessageContent(type="text", text=input.input)]))
            for message in map_assistant_completion_response_to_chat_messages(assistant_response):
                conv.add_message(message)
        else:
            #conv.add_message(ChatMessage(role="system", content=[ChatMessageContent(type="text", text="Unknown error occurred.")]))
            raise ValueError("Unknown response type from assistant.")

        return conv
    except Exception as e:
        print(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=str(e))


@router.get("/{assistant_id}/chats/{conversation_id}", response_model=ChatConversation)
def get_conversation(assistant_id: str, conversation_id: str, user = Depends(dep_current_user)):
    try:
        _assistant = init_assistant_for_user(user["username"], assistant_id, conversation_id)
        #memory = get_chat_memory(user["username"], assistant, conversation_id, create=False)
        if _assistant.memory:
            messages = _assistant.memory.get_messages()
        else:
            messages = ChatMessage(role="system", content=[ChatMessageContent(type="text", text="No conversation history found.")])
        conv = ChatConversation(id=conversation_id, messages=messages)
        return conv
    except FileNotFoundError:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND,)



@router.post("/{assistant_id}/chats/{conversation_id}", response_model=ChatConversation)
def process_user_message(assistant_id: str, conversation_id: str, input: AssistantChatInputRequest, user = Depends(dep_current_user)):

    # def message_generator(num_messages: int = 3) -> Generator[str, None, None]:
    #     for i in range(num_messages):
    #         yield f"Message part {i + 1}\n"

    conv = ChatConversation(id=conversation_id, messages=[], is_partial=True)
    user_msg = ChatMessage(role="user", content=[ChatMessageContent(type="text", text=input.input)])
    conv.messages.append(user_msg)

    try:
        _assistant = init_assistant_for_user(user["username"], assistant_id, conversation_id)

        # a dummy assistant response that echoes the user input
        dummy_msg = ChatMessage(role="assistant", content=[
            ChatMessageContent(type="text", text=f"You said: {input.input}")
        ])
        conv.messages.append(dummy_msg)
        # another assistant response that indicates an assistant task
        # task_msg = ChatMessage(
        #     role="system",
        #     content=[ChatMessageContent(type="task", data={"task_id": str(uuid.uuid4().hex)}, text="A task has been created.")]
        # )
        # conv.messages.append(task_msg)
        # save dummy messages to memory
        if _assistant.memory:
            _assistant.memory.add_message(dummy_msg)
            #_assistant.memory.add_message(task_msg)

        assistant_response = _assistant.prompt(input.input)
        for message in map_assistant_completion_response_to_chat_messages(assistant_response):
            conv.add_message(message)

        # simulate streaming by yielding parts of the assistant message
        # content = []
        # for part in message_generator():
        #     content.append(ChatMessageContent(type="text", text=part))
        # generator_msg = ChatMessage(role="assistant", content=content)
        # conv.messages.append(generator_msg)

        # return the partial conversation
        return conv
    except FileNotFoundError:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND,)


def map_assistant_completion_response_to_chat_messages(response: CompletionResponse) -> List[ChatMessage]:
    """
    Map the assistant response to a list of ChatMessage objects.
    """
    messages = []

    if response.output:
        for output_item in response.output:
            content_items = []
            for content in output_item.get("content", []):
                if content["type"] == "output_text":
                    content_items.append(ChatMessageContent(type="text", text=content["text"]))
                elif content["type"] == "function_call":
                    content_items.append(ChatMessageContent(type="function", data=content, text=content.get("text", "")))
                # todo handle other content types

            message = ChatMessage(
                role="assistant",
                content=content_items
            )
            messages.append(message)
    return messages