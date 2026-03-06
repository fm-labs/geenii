import json
import uuid
from typing import Annotated, Literal, Any
import datetime

import pydantic
from pydantic import BaseModel, Field


# --- Content Part Models ---

class BaseContent(BaseModel):
    type: str

    def to_text(self) -> str:
        return f"[{self.type} content]"


class TextContent(BaseContent):
    type: Literal["text"] = "text"
    text: str

    def to_text(self) -> str:
        return self.text


class ImageContent(BaseContent):
    type: Literal["image"] = "image"
    url: str
    alt: str | None = None


class AudioContent(BaseContent):
    type: Literal["audio"] = "audio"
    url: str
    duration: float | None = None


class FunctionCallContent(BaseContent):
    type: Literal["function"] = "function"
    name: str
    arguments: dict | None = None
    result: str | None = None

    def to_text(self) -> str:
        args_str = ", ".join(f"{k}={v!r}" for k, v in (self.arguments or {}).items())
        return f"Function call request: {self.name}({args_str})"


class ToolCallContent(BaseContent):
    type: Literal["tool_call"] = "tool_call"
    name: str
    arguments: dict | None = None
    call_id: str | None = None  # Unique call ID
    require_approval: bool = False  # True, if HIDL approval is required before executing the tool
    approval_id: str | None = None  # Unique approval ID for HIDL, if require_approval is True

    def to_text(self) -> str:
        args_str = ", ".join(f"{k}={v!r}" for k, v in (self.arguments or {}).items())
        return f"Tool call request (call_id={self.call_id}): {self.name}({args_str})]"


class ToolCallResultContent(BaseContent):
    type: Literal["tool_call_result"] = "tool_call_result"
    call_id: str | None = None
    name: str
    arguments: dict | None = pydantic.Field(default_factory=dict)
    result: dict | list | str | Any | None = None
    error: str | None = None  # Optional error message if the tool call failed

    def to_text(self) -> str:
        if self.error:
            return f"Tool call result for {self.name} (call_id={self.call_id}): ERROR: {self.error}"
        else:
            return f"Tool call result for {self.name} (call_id={self.call_id}): {self.result!r}"


class FileContent(BaseContent):
    type: Literal["file"] = "file"
    url: str
    filename: str
    content_type: str | None = None
    size: int | None = None

    def to_text(self) -> str:
        return f"File: {self.filename} ({self.content_type}, {self.size} bytes) at {self.url}"


class EmbedContent(BaseContent):
    type: Literal["embed"] = "embed"
    title: str | None = None
    description: str | None = None
    url: str | None = None
    thumbnail_url: str | None = None
    video_url: str | None = None

    def to_text(self) -> str:
        parts = [f"Embed: {self.title or 'No title'}"]
        if self.description:
            parts.append(f"Description: {self.description}")
        if self.url:
            parts.append(f"URL: {self.url}")
        if self.thumbnail_url:
            parts.append(f"Thumbnail: {self.thumbnail_url}")
        if self.video_url:
            parts.append(f"Video: {self.video_url}")
        return "\n".join(parts)


class JsonContent(BaseContent):
    type: Literal["json"] = "json"
    data: dict | list

    def to_text(self) -> str:
        return json.dumps(self.data)


class UserConfirmationContent(BaseContent):
    type: Literal["confirmation"] = "confirmation"
    confirmation_id: str = Field(default_factory=lambda: uuid.uuid4().hex)  # Unique confirmation ID
    text: str = ""  # Prompt or question for the user
    confirmed: bool | None = None  # True if user confirmed, False if rejected, None if not responded yet

    def to_text(self) -> str:
        status = "Confirmed" if self.confirmed else "Rejected" if self.confirmed is False else "Pending"
        return f"UserConfirmation (id={self.confirmation_id}): {self.text} [Status: {status}]"


class UserInteractionContent(BaseContent):
    type: Literal["interaction"] = "interaction"
    interaction_id: str = Field(default_factory=lambda: uuid.uuid4().hex)  # Unique interaction ID
    interaction_type: str
    text: str = ""  # Prompt or question for the user
    choices: list[str] = Field(default_factory=list)  # List of valid choices for the user
    choice: str | None = None  # The user's choice (if applicable)

    def to_text(self) -> str:
        choices_str = ", ".join(self.choices)
        return f"UserInteraction (id={self.interaction_id}): choices=[{choices_str}] selected={self.choice!r}"


ContentPart = Annotated[
    TextContent | ImageContent | AudioContent | FileContent | EmbedContent |
    FunctionCallContent | ToolCallContent | ToolCallResultContent | JsonContent |
    UserInteractionContent | UserConfirmationContent,
    Field(discriminator="type"),
]


# --- Message Models ---

class MessageCreate(BaseModel):
    content: list[ContentPart]


# --- Wire Message Models (connection/queue level, no DB id/created_at) ---

class ChatMessage(BaseModel):
    """A user or bot message travelling through the connection layer."""
    type: Literal["message"] = "message"
    room_id: str
    sender_id: str
    content: list[ContentPart]
    id: str = pydantic.Field(default_factory=lambda: uuid.uuid4().hex)
    created_at: int = pydantic.Field(default_factory=lambda: int(datetime.datetime.now().timestamp() * 1000)) # default to current timestamp in milliseconds


class SystemMessage(BaseModel):
    """A server-generated notification (join, leave, status, etc.)."""
    type: Literal["system"] = "system"
    room_id: str
    content: str


WireMessage = ChatMessage | SystemMessage


# --- Room Models ---

RoomType = Literal["group", "dm"]


class RoomCreate(BaseModel):
    name: str
    is_public: bool = False
    password: str | None = None
    room_type: RoomType = "group"
    dm_peer: str | None = None  # required when room_type == "dm"


class Room(BaseModel):
    id: str
    name: str
    owner: str
    is_public: bool
    room_type: RoomType
    created_at: str


# --- Member Models ---

class JoinRoom(BaseModel):
    username: str
    password: str | None = None
    member_type: Literal["user", "bot"] = "user"


class LeaveRoom(BaseModel):
    username: str


class InviteUser(BaseModel):
    username: str
    member_type: Literal["user", "bot"] = "user"


class Member(BaseModel):
    id: int
    room_id: str
    username: str
    member_type: str
    status: str
    joined_at: str


