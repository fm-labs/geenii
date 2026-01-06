import time
import uuid

import pydantic
from pydantic import ConfigDict


class ChatMessageContent(pydantic.BaseModel):
    #model_config = ConfigDict()

    id: str = pydantic.Field(default_factory=lambda: uuid.uuid4().hex)
    type: str # e.g., "text", "image", "code"
    text: str | None = None  # e.g., for text content
    data: dict | None = None  # e.g., for images or other media
    function: dict | None = None  # e.g., {"name": "function_name", "arguments": {...}}
    #timestamp: int | None = pydantic.Field(default_factory=lambda: int(pydantic.datetime.datetime.utcnow().timestamp()))

    def model_dump(self, **kwargs) -> dict:
        return super().model_dump(exclude_none=True, **kwargs)

class ChatMessage(pydantic.BaseModel):
    id : str = pydantic.Field(default_factory=lambda: uuid.uuid4().hex)
    #sender_id: str = pydantic.Field(default_factory=lambda: pydantic.uuid4().hex)
    role: str  # e.g., "user", "assistant", "system"
    content: list[ChatMessageContent] = pydantic.Field(default_factory=list)
    timestamp: int | None = pydantic.Field(default_factory=lambda: int(time.time() * 1000))


class ChatConversation(pydantic.BaseModel):
    id: str = pydantic.Field(default_factory=lambda: uuid.uuid4().hex)
    messages: list[ChatMessage] = pydantic.Field(default_factory=list)
    metadata: dict | None = None  # e.g., {"title": "Conversation Title", "created_at": "..."}
    is_partial: bool = False  # Indicates if the conversation is complete or partial
    timestamp: int | None = pydantic.Field(default_factory=lambda: int(time.time() * 1000))

    def add_message(self, message: ChatMessage) -> None:
        self.messages.append(message)
