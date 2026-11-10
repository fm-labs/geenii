import json
import uuid
from typing import Annotated, Literal, Any

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
    url: str | None = None
    base64: str | None = None
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
    require_approval: bool = (
        False  # True, if HITL approval is required before executing the tool
    )
    approval_id: str | None = (
        None  # Unique approval ID for HITL, if require_approval is True
    )

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
    confirmation_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex
    )  # Unique confirmation ID
    text: str = ""  # Prompt or question for the user
    confirmed: bool | None = (
        None  # True if user confirmed, False if rejected, None if not responded yet
    )

    def to_text(self) -> str:
        status = (
            "Confirmed"
            if self.confirmed
            else "Rejected"
            if self.confirmed is False
            else "Pending"
        )
        return f"UserConfirmation (id={self.confirmation_id}): {self.text} [Status: {status}]"


class UserInteractionContent(BaseContent):
    type: Literal["interaction"] = "interaction"
    interaction_id: str = Field(
        default_factory=lambda: uuid.uuid4().hex
    )  # Unique interaction ID
    interaction_type: str
    text: str = ""  # Prompt or question for the user
    choices: list[str] = Field(
        default_factory=list
    )  # List of valid choices for the user
    choice: str | None = None  # The user's choice (if applicable)

    def to_text(self) -> str:
        choices_str = ", ".join(self.choices)
        return f"UserInteraction (id={self.interaction_id}): choices=[{choices_str}] selected={self.choice!r}"


class WidgetContent(BaseContent):
    type: Literal["widget"] = "widget"
    name: str  # Widget name in dot-notation, e.g. "geenii.table" or "geenii.clock"
    data: dict | list | Any | None = None  # Passed to the widget as-is
    heading: str | None = (
        None  # Shown in a small header above the widget (unlike titles inside `data`)
    )
    text: str | None = None  # Shown if the UI does not know the widget

    def to_text(self) -> str:
        text = self.text or f"[widget: {self.name}]"
        return f"{self.heading}\n{text}" if self.heading else text


ContentPart = Annotated[
    TextContent
    | ImageContent
    | AudioContent
    | FileContent
    | EmbedContent
    | FunctionCallContent
    | ToolCallContent
    | ToolCallResultContent
    | JsonContent
    | UserInteractionContent
    | UserConfirmationContent
    | WidgetContent,
    Field(discriminator="type"),
]
