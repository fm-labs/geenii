from __future__ import annotations

from typing import Any

from abc import ABC, abstractmethod


class Tool(ABC):
    """Abstract base for all tool types."""

    def __init__(self, name: str, description: str = "", parameters: dict | None = None):
        self.type = "tool"
        self.name = name
        self.description = description
        self.parameters = parameters or {}

    #def __str__(self) -> str:
    #    return self.name

    #def __repr__(self) -> str:
    #    return f"<{self.__class__.__name__} name={self.name!r}>"

    @abstractmethod
    async def invoke(self, args: dict[str,Any], env: dict[str, str] | None = None, **kwargs: Any) -> Any:
        ...

    @property
    def short_description(self) -> str:
        return self.description.strip().split("\n")[0] if self.description else "no description"

    def to_definition(self) -> dict:
        """Return an OpenAI-compatible tool definition."""
        return {
            "type": self.type,
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def to_openai(self) -> dict:
        """Return an OpenAI-compatible tool definition."""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }

    def to_ollama(self) -> dict:
        """Return an Ollama-compatible tool definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


def expand_vars(command: str, env: dict[str, str]) -> str:
    """Expand environment variables in a command string."""
    for key, value in env.items():
        command = command.replace(f"${{{key}}}", value)
        command = command.replace(f"${key}", value)
    return command
