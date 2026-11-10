import logging
import queue
import threading
from typing import Iterator

from geenii.agent.base_agent import BaseAgent
from geenii.chat_models import (
    ContentPart,
    ToolCallResultContent,
    UserInteractionContent,
)
from geenii.datamodels import (
    ChatDoneEvent,
    ChatErrorEvent,
    ChatMessage,
    ChatMessageEvent,
    ChatStatusEvent,
    ChatStreamEvent,
    ModelMessage,
)
from geenii.hitl import WebHumanInTheLoopController

logger = logging.getLogger(__name__)

_END = object()


class AgentBusyError(RuntimeError):
    """The conversation already has a running turn."""


class WebAgentRunner:
    """
    Runs one agent conversation for web clients.

    - One turn at a time: `start()` raises AgentBusyError while a turn is running.
    - The turn runs in its own thread and always runs to completion (or cancellation), independent of the
      consumer of the returned event stream, so a client that disconnects never leaves the conversation busy.
    - Tool approvals: approval requests are streamed to the client, which answers them via `respond()`.
    - `cancel()` rejects pending approvals and ends the turn at the next message.
    """

    def __init__(self, agent: BaseAgent, hitl: WebHumanInTheLoopController):
        self.agent = agent
        self.hitl = hitl
        self._turn = threading.Lock()
        self._cancelled = threading.Event()

    @property
    def busy(self) -> bool:
        return self._turn.locked()

    def envelope(self, message: ModelMessage) -> ChatMessage:
        return ChatMessage(
            id=message.id,
            timestamp=message.timestamp,
            sender_id="user" if message.role == "user" else self.agent.name,
            context_id=self.agent.context_id,
            message=message,
        )

    def start(self, content: str | list[ContentPart]) -> Iterator[ChatStreamEvent]:
        """Start a turn and return its event stream (ends after a `done` or `error` event)."""
        if not self._turn.acquire(blocking=False):
            raise AgentBusyError(f"Conversation {self.agent.context_id} is busy")
        self._cancelled.clear()
        self.hitl.reset()

        events: queue.Queue = queue.Queue()
        threading.Thread(
            target=self._run_turn,
            args=(content, events),
            daemon=True,
            name=f"agent-turn-{self.agent.context_id}",
        ).start()
        return self._read(events)

    @staticmethod
    def _read(events: queue.Queue) -> Iterator[ChatStreamEvent]:
        while (event := events.get()) is not _END:
            yield event

    def _run_turn(self, content: str | list[ContentPart], events: queue.Queue) -> None:
        messages = self.agent.process(content)
        final: ChatStreamEvent = ChatDoneEvent()
        try:
            events.put(ChatStatusEvent(status="thinking"))
            for message in messages:
                if self._cancelled.is_set():
                    break
                interaction_ids = [
                    p.interaction_id
                    for p in message.content
                    if isinstance(p, UserInteractionContent)
                ]
                for interaction_id in interaction_ids:
                    # answerable from now on, even before the agent starts waiting
                    self.hitl.expect(interaction_id)

                events.put(ChatMessageEvent(message=self.envelope(message)))

                if interaction_ids:
                    events.put(ChatStatusEvent(status="awaiting_input"))
                elif any(isinstance(p, ToolCallResultContent) for p in message.content):
                    events.put(ChatStatusEvent(status="thinking"))
        except Exception as e:
            logger.exception(
                f"Agent run failed for context {self.agent.context_id}", exc_info=e
            )
            final = ChatErrorEvent(error=str(e))
        finally:
            messages.close()
            # a cancelled or failed turn may leave tasks behind; they must not run with the next message
            self.agent.clear_tasks()
            self._turn.release()
            events.put(final)
            events.put(_END)

    def respond(self, interaction_id: str, choice: str) -> bool:
        """Answer a pending approval request. Returns False if it is not pending."""
        return self.hitl.respond(interaction_id, choice)

    def cancel(self) -> None:
        self._cancelled.set()
        self.hitl.cancel()
