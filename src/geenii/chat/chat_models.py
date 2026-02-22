from typing import Annotated, Literal, Any

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

class ToolCallContent(BaseContent):
    type: Literal["tool_call"] = "tool_call"
    name: str
    arguments: dict | None = None
    call_id: str | None = None  # Unique identifier for this tool call, useful for matching with results


class ToolCallResultContent(BaseContent):
    type: Literal["tool_call_result"] = "tool_call_result"
    call_id: str | None = None
    name: str
    arguments: dict | None = None
    result: dict | list | str | Any | None = None
    error: str | None = None  # Optional error message if the tool call failed


class FileContent(BaseContent):
    type: Literal["file"] = "file"
    url: str
    filename: str
    content_type: str | None = None
    size: int | None = None


class EmbedContent(BaseContent):
    type: Literal["embed"] = "embed"
    title: str | None = None
    description: str | None = None
    url: str | None = None
    thumbnail_url: str | None = None
    video_url: str | None = None



ContentPart = Annotated[
    TextContent | ImageContent | AudioContent | FileContent | EmbedContent |
    FunctionCallContent | ToolCallContent | ToolCallResultContent,
    Field(discriminator="type"),
]



# --- Message Models ---

class MessageCreate(BaseModel):
    content: list[ContentPart]


class Message(BaseModel):
    id: int
    room_id: str
    username: str
    content: list[ContentPart]
    created_at: str



# --- Wire Message Models (connection/queue level, no DB id/created_at) ---

class ChatMessage(BaseModel):
    """A user or bot message travelling through the connection layer."""
    type: Literal["message"] = "message"
    room_id: str
    sender_id: str
    content: list[ContentPart]


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


