from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from abc import ABC, abstractmethod


@dataclass
class ToolCallResult:
    text: str
    structured_content: dict[str, Any] | None = None
    is_error: bool = False


@dataclass
class ToolCallContext:
    cwd: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    caller_id: str | None = None


class Tool(ABC):
    """Abstract base for all tool types."""

    def __init__(
        self, name: str, description: str = "", input_schema: dict | None = None
    ):
        self.type = "tool"
        self.name = name
        self.description = description
        self.input_schema = input_schema or {}

    # def __str__(self) -> str:
    #    return self.name

    # def __repr__(self) -> str:
    #    return f"<{self.__class__.__name__} name={self.name!r}>"

    @abstractmethod
    def invoke(
        self,
        args: dict[str, Any],
        env: dict[str, str] | None = None,
        *,
        ctx: ToolCallContext,
    ) -> ToolCallResult: ...

    @property
    def short_description(self) -> str:
        return (
            self.description.strip().split("\n")[0]
            if self.description
            else "no description"
        )

    def to_definition(self) -> dict:
        """Return an OpenAI-compatible tool definition."""
        return {
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema,
        }

    def to_openai(self) -> dict:
        """Return an OpenAI-compatible tool definition."""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.input_schema,
        }

    def to_ollama(self) -> dict:
        """Return an Ollama-compatible tool definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


_VAR_PATTERN = re.compile(r"\$\{(\w+)\}|\$(\w+)")


def expand_vars(command: str, env: dict[str, str]) -> str:
    """Expand ${NAME} and $NAME from env in a command string. Unknown names are left for the shell."""

    def replace(m: re.Match) -> str:
        name = m.group(1) or m.group(2)
        return str(env[name]) if name in env else m.group(0)

    # one pass, matching whole names: $AB is never expanded as $A + "B", and values are not expanded again
    return _VAR_PATTERN.sub(replace, command)


def to_tool_call_result(result: Any) -> ToolCallResult:
    """Map a handler's return value to a ToolCallResult. `text` is always a string; dicts are also structured content."""
    if isinstance(result, Exception):
        return ToolCallResult(text=str(result), is_error=True)
    if isinstance(result, ToolCallResult):
        return result
    if result is None:
        return ToolCallResult(text="")
    if isinstance(result, str):
        return ToolCallResult(text=result)
    if isinstance(result, bytes):
        return ToolCallResult(text=result.decode("utf-8", errors="replace"))
    if isinstance(result, dict):
        return ToolCallResult(
            text=json.dumps(result, default=str), structured_content=result
        )
    if isinstance(result, (list, tuple)):
        return ToolCallResult(text=json.dumps(result, default=str))
    return ToolCallResult(text=str(result))
