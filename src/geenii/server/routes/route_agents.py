import uuid
import json
import os
from typing import List

import pydantic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ConfigDict
from starlette import status

from geenii.chat.memory import ChatMemory, FileChatMemory
from geenii.chat.models import ChatConversation, ChatMessageContent, ChatMessage
from geenii.datamodels import CompletionApiResponse
from geenii.server.deps import dep_current_user
from geenii.settings import DATA_DIR
from geenii.wizard.default import DefaultWizard

router = APIRouter(prefix="/ai/v1/agents", tags=["chats"])

def get_chat_memory(username: str, agentname: str, conversation_id: str, create=False) -> ChatMemory:
    # using a file based chat memory for simplicity
    file_path = f"{DATA_DIR}/chats/{username}/{agentname}/{conversation_id}/memory.json"
    print(f"Loading chat memory from {file_path}", create)
    return FileChatMemory(file_path, create=create)


def find_conversations_for_user_in_dir(username: str, agentname: str) -> list[str]:
    base_path = f"{DATA_DIR}/chats/{username}/{agentname}/"
    # subfolders are conversation IDs
    if not os.path.exists(base_path):
        return []
    return [name for name in os.listdir(base_path)
            if os.path.isdir(os.path.join(base_path, name))]


def fetch_agent_configs_for_user(username: str) -> list[dict]:
    #agents_json_file = f"{DATA_DIR}/users/{username}/agents.json"
    agents_json_file = f"{DATA_DIR}/agents.json"
    import os
    if not os.path.exists(agents_json_file):
        return []
    with open(agents_json_file, 'r') as f:
        data = json.load(f)
        return data


def init_agent_for_user(username: str, agentname: str, conversation_id: str, create=False) -> DefaultWizard:
    memory = get_chat_memory(username, agentname, conversation_id, create=create)
    agent = DefaultWizard(memory=memory, context_id=conversation_id)
    return agent



class AgentChatInputRequest(pydantic.BaseModel):
    model_config = ConfigDict(extra="allow")
    input: str


class AgentConfig(pydantic.BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    name: str
    description: str | None = None


@router.get("/")
async def list_available_agents(user = Depends(dep_current_user)) -> List[AgentConfig]:
    """
    List all available agentic AI agents.
    """
    agent_configs_dict = fetch_agent_configs_for_user(user["username"])
    return [AgentConfig(**agent) for agent in agent_configs_dict]


@router.post("/")
def create_agent(agent_config: AgentConfig, user = Depends(dep_current_user)) -> AgentConfig:
    pass


@router.post("/{agent}")
def configure_agent(agent: str, agent_config: AgentConfig, user = Depends(dep_current_user)) -> AgentConfig:
    pass


@router.get("/{agent}/chats", response_model=List[ChatConversation])
def list_conversations(agent: str, user = Depends(dep_current_user)):
    ids = find_conversations_for_user_in_dir(user["username"], agent)
    conversations = []
    for conv_id in ids:
        conversations.append(ChatConversation(id=conv_id))
    return conversations


@router.post("/{agent}/chats", response_model=ChatConversation)
def create_conversation(agent: str, input: AgentChatInputRequest, user = Depends(dep_current_user)):
    try:
        conversion_id = str(uuid.uuid4().hex)

        # get the default agent for the user
        _agent = init_agent_for_user(user["username"], agent, conversion_id, create=True)
        # create a new conversation with the user input as the first message
        agent_response = _agent.prompt(input.input)

        conv = ChatConversation(id=conversion_id, messages=[])
        conv.add_message(ChatMessage(role="user", content=[ChatMessageContent(type="text", text=input.input)]))
        for message in map_agent_response_to_chat_messages(agent_response):
            conv.add_message(message)

        return conv
    except Exception as e:
        print(e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=str(e))


@router.get("/{agent}/chats/{conversation_id}", response_model=ChatConversation)
def get_conversation(agent: str, conversation_id: str, user = Depends(dep_current_user)):
    try:
        _agent = init_agent_for_user(user["username"], agent, conversation_id)
        #memory = get_chat_memory(user["username"], agent, conversation_id, create=False)
        if _agent.memory:
            messages = _agent.memory.get_messages()
        else:
            messages = ChatMessage(role="system", content=[ChatMessageContent(type="text", text="No conversation history found.")])
        conv = ChatConversation(id=conversation_id, messages=messages)
        return conv
    except FileNotFoundError:
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND,)



@router.post("/{agent}/chats/{conversation_id}", response_model=ChatConversation)
def process_user_message(agent: str, conversation_id: str, input: AgentChatInputRequest, user = Depends(dep_current_user)):

    # def message_generator(num_messages: int = 3) -> Generator[str, None, None]:
    #     for i in range(num_messages):
    #         yield f"Message part {i + 1}\n"

    conv = ChatConversation(id=conversation_id, messages=[], is_partial=True)
    user_msg = ChatMessage(role="user", content=[ChatMessageContent(type="text", text=input.input)])
    conv.messages.append(user_msg)

    try:
        _agent = init_agent_for_user(user["username"], agent, conversation_id)

        # a dummy assistant response that echoes the user input
        dummy_msg = ChatMessage(role="assistant", content=[
            ChatMessageContent(type="text", text=f"You said: {input.input}")
        ])
        conv.messages.append(dummy_msg)
        # another assistant response that indicates an agent task
        # task_msg = ChatMessage(
        #     role="system",
        #     content=[ChatMessageContent(type="task", data={"task_id": str(uuid.uuid4().hex)}, text="A task has been created.")]
        # )
        # conv.messages.append(task_msg)
        # save dummy messages to memory
        if _agent.memory:
            _agent.memory.add_message(dummy_msg)
            #_agent.memory.add_message(task_msg)

        agent_response = _agent.prompt(input.input)
        for message in map_agent_response_to_chat_messages(agent_response):
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


def map_agent_response_to_chat_messages(response: CompletionApiResponse) -> List[ChatMessage]:
    """
    Map the agent response to a list of ChatMessage objects.
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