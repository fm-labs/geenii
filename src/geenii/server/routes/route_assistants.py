import uuid
import json
import os
from typing import List

import pydantic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import ConfigDict
from starlette import status

from geenii.memory import ChatMemory, FileChatMemory
from geenii.server.deps import dep_current_user
from geenii.config import DATA_DIR

router = APIRouter(prefix="/assistants", tags=["agents"])


class AgentChatInputRequest(pydantic.BaseModel):
    model_config = ConfigDict(extra="allow")

    input: str


class AgentConfigRequestBody(pydantic.BaseModel):
    model_config = ConfigDict(extra="allow") # todo remove extra allow once implemented

    name: str
    description: str | None = None
    model: str | None = None
    model_parameters: dict | None = None
    system_prompt: str | None = None


class AgentConfig(AgentConfigRequestBody):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    description: str | None = None
    model: str | None = None
    model_parameters: dict | None = pydantic.Field(default_factory=dict)
    system_prompt: str | None = None



# @router.get("/")
# async def list_available_agents(user = Depends(dep_current_user)) -> List[AgentConfig]:
#     """
#     List all available agentic AI agents.
#     """
#     agent_configs_dict = fetch_agent_configs_for_user(user["username"])
#     return [AgentConfig(**agent) for agent in agent_configs_dict]
#
#
# @router.post("/")
# def create_agent(agent_config: AgentConfigRequestBody, user = Depends(dep_current_user)) -> AgentConfig:
#     # create a new agent config and save it
#     new_agent = AgentConfig(
#         id=str(uuid.uuid4().hex),
#         name=agent_config.name,
#         description=agent_config.description,
#         model=agent_config.model,
#         model_parameters=agent_config.model_parameters or {},
#         system_prompt=agent_config.system_prompt
#     )
#     print("Creating new agent:", new_agent)
#     update_agent_config_for_user(user["username"], new_agent.model_dump())
#     return new_agent
#
#
# @router.post("/{agent_id}")
# def configure_agent(agent_id: str, agent_config: AgentConfigRequestBody, user = Depends(dep_current_user)) -> AgentConfig:
#     agent_dict = fetch_agent_config_by_id_for_user(user["username"], agent_id)
#     if not agent_dict:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
#     # update the agent config
#     updated_agent_config = AgentConfig(**agent_dict).model_copy(update=agent_config.model_dump())
#     print("Updating agent:", updated_agent_config)
#     update_agent_config_for_user(user["username"], updated_agent_config.model_dump())
#     return updated_agent_config


# @router.get("/{agent_id}/chats", response_model=List[ModelConversation])
# def list_conversations(agent_id: str, user = Depends(dep_current_user)):
#     ids = find_conversations_for_user_in_dir(user["username"], agent_id)
#     conversations = []
#     for conv_id in ids:
#         conversations.append(ModelConversation(id=conv_id))
#     return conversations
#
#
# @router.post("/{agent_id}/chats", response_model=ModelConversation)
# def create_conversation(agent_id: str, input: AgentChatInputRequest, user = Depends(dep_current_user)):
#     try:
#         conversion_id = str(uuid.uuid4().hex)
#         conv = ModelConversation(id=conversion_id, messages=[])
#
#         # get the default agent for the user
#         _agent = init_agent_for_user(user["username"], agent_id, conversion_id, create=True)
#         # create a new conversation with the user input as the first message
#         agent_response = _agent.prompt(input.input)
#         # handle error response
#         if isinstance(agent_response, CompletionErrorResponse):
#             conv.append(ModelMessage(role="system", content=[ContentPart(type="text", text=f"Error: {agent_response.error_message}")]))
#         elif isinstance(agent_response, CompletionResponse):
#             conv.append(ModelMessage(role="user", content=[ContentPart(type="text", text=input.input)]))
#             for message in map_agent_completion_response_to_chat_messages(agent_response):
#                 conv.append(message)
#         else:
#             #conv.add_message(ChatMessage(role="system", content=[ChatMessageContent(type="text", text="Unknown error occurred.")]))
#             raise ValueError("Unknown response type from agent.")
#
#         return conv
#     except Exception as e:
#         print(e)
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                             detail=str(e))
#
#
# @router.get("/{agent_id}/chats/{conversation_id}", response_model=ModelConversation)
# def get_conversation(agent_id: str, conversation_id: str, user = Depends(dep_current_user)):
#     try:
#         _agent = init_agent_for_user(user["username"], agent_id, conversation_id)
#         #memory = get_chat_memory(user["username"], agent, conversation_id, create=False)
#         if _agent.memory:
#             messages = _agent.memory.messages()
#         else:
#             messages = ModelMessage(role="system", content=[ContentPart(type="text", text="No conversation history found.")])
#         conv = ModelConversation(id=conversation_id, messages=messages)
#         return conv
#     except FileNotFoundError:
#         return HTTPException(status_code=status.HTTP_404_NOT_FOUND,)
#
#
#
# @router.post("/{agent_id}/chats/{conversation_id}", response_model=ModelConversation)
# def process_user_message(agent_id: str, conversation_id: str, input: AgentChatInputRequest, user = Depends(dep_current_user)):
#
#     # def message_generator(num_messages: int = 3) -> Generator[str, None, None]:
#     #     for i in range(num_messages):
#     #         yield f"Message part {i + 1}\n"
#
#     conv = ModelConversation(id=conversation_id, messages=[], is_partial=True)
#     user_msg = ModelMessage(role="user", content=[ContentPart(type="text", text=input.input)])
#     conv.messages.append(user_msg)
#
#     try:
#         _agent = init_agent_for_user(user["username"], agent_id, conversation_id)
#
#         # a dummy agent response that echoes the user input
#         dummy_msg = ModelMessage(role="agent", content=[
#             ContentPart(type="text", text=f"You said: {input.input}")
#         ])
#         conv.messages.append(dummy_msg)
#         # another agent response that indicates an agent task
#         # task_msg = ChatMessage(
#         #     role="system",
#         #     content=[ChatMessageContent(type="task", data={"task_id": str(uuid.uuid4().hex)}, text="A task has been created.")]
#         # )
#         # conv.messages.append(task_msg)
#         # save dummy messages to memory
#         if _agent.memory:
#             _agent.memory.append(dummy_msg)
#             #_agent.memory.add_message(task_msg)
#
#         agent_response = _agent.prompt(input.input)
#         for message in map_agent_completion_response_to_chat_messages(agent_response):
#             conv.append(message)
#
#         # simulate streaming by yielding parts of the agent message
#         # content = []
#         # for part in message_generator():
#         #     content.append(ChatMessageContent(type="text", text=part))
#         # generator_msg = ChatMessage(role="agent", content=content)
#         # conv.messages.append(generator_msg)
#
#         # return the partial conversation
#         return conv
#     except FileNotFoundError:
#         return HTTPException(status_code=status.HTTP_404_NOT_FOUND,)


# def map_agent_completion_response_to_chat_messages(response: CompletionResponse) -> List[ModelMessage]:
#     """
#     Map the agent response to a list of ChatMessage objects.
#     """
#     messages = []
#
#     if response.output:
#         for output_item in response.output:
#             content_items = []
#             for content in output_item.get("content", []):
#                 if content["type"] == "output_text":
#                     content_items.append(ContentPart(type="text", text=content["text"]))
#                 elif content["type"] == "function_call":
#                     content_items.append(ContentPart(type="function", data=content, text=content.get("text", "")))
#                 # todo handle other content types
#
#             message = ModelMessage(
#                 role="agent",
#                 content=content_items
#             )
#             messages.append(message)
#     return messages