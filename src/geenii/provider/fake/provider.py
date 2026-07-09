"""Deterministic fake provider for testing the agent loop without network access."""

import time
import uuid
from collections import deque
from typing import List

from geenii.chat_models import TextContent, ToolCallContent, ContentPart
from geenii.datamodels import (
    AIModelInfo,
    ChatCompletionRequest,
    ChatCompletionResponse,
    CompletionResponse,
)
from geenii.provider.interfaces import AIProvider, AICompletionProvider, AIChatCompletionProvider


class FakeProvider(AIProvider, AICompletionProvider, AIChatCompletionProvider):
    """A test provider that returns pre-configured responses.

    Usage::

        provider = FakeProvider()
        # Queue simple text responses
        provider.enqueue("Hello from the fake model!")
        provider.enqueue("Follow-up response.")

        # Queue a response with tool calls
        provider.enqueue_tool_call("get_weather", {"city": "Vienna"})

        # Responses are returned in FIFO order.
        # After all queued responses are consumed, a default fallback is returned.
    """

    DEFAULT_MODEL = "fake:test"

    def __init__(self, **kwargs):
        super().__init__(name="fake")
        self._responses: deque[List[ContentPart]] = deque()
        self.requests: list[ChatCompletionRequest] = []
        self.default_response = "I am a fake model."

    def enqueue(self, text: str) -> None:
        """Queue a plain-text response."""
        self._responses.append([TextContent(text=text)])

    def enqueue_parts(self, parts: List[ContentPart]) -> None:
        """Queue a response with arbitrary content parts."""
        self._responses.append(parts)

    def enqueue_tool_call(self, name: str, arguments: dict | None = None, call_id: str | None = None) -> None:
        """Queue a response that requests a tool call."""
        self._responses.append([
            ToolCallContent(
                name=name,
                arguments=arguments or {},
                call_id=call_id or ("fake_call_" + uuid.uuid4().hex[:8]),
            )
        ])

    def reset(self) -> None:
        """Clear queued responses and recorded requests."""
        self._responses.clear()
        self.requests.clear()

    def is_configured(self) -> bool:
        return True

    def get_capabilities(self) -> list[str]:
        return ["completion", "chat_completion", "tool_calling"]

    def get_models(self) -> list[AIModelInfo]:
        return [
            AIModelInfo(
                name="test",
                provider=self.name,
                description="Deterministic fake model for testing",
                capabilities=["completion", "chat_completion", "tool_calling"],
                locality="local",
                installed=True,
            )
        ]

    def generate_completion(self, prompt: str, **kwargs) -> CompletionResponse:
        text = self._responses.popleft()[0].text if self._responses else self.default_response
        return CompletionResponse(
            id=uuid.uuid4().hex,
            timestamp=int(time.time()),
            model=f"{self.name}:test",
            output=[TextContent(text=text)],
            output_text=text,
            model_result={},
        )

    def generate_chat_completion(self, request: ChatCompletionRequest, tool_registry=None) -> ChatCompletionResponse:
        self.requests.append(request)

        if self._responses:
            output_parts = list(self._responses.popleft())
        else:
            output_parts = [TextContent(text=self.default_response)]

        usage = {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}

        return ChatCompletionResponse(
            id=uuid.uuid4().hex,
            timestamp=int(time.time()),
            model=f"{self.name}:test",
            prompt=request.prompt,
            output=output_parts,
            model_result={},
            usage=usage,
        )


ai_provider_class = FakeProvider
