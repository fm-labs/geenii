import logging
import re
import shutil
import threading
import uuid
from collections import OrderedDict
from datetime import datetime, UTC
from pathlib import Path

import pydantic

from geenii.agent.registry import AgentRegistry
from geenii.g import init_agent
from geenii.datamodels import ModelMessage
from geenii.hitl import WebHumanInTheLoopController
from geenii.memory import FileChatMemory
from geenii.server.web_runner import WebAgentRunner

logger = logging.getLogger(__name__)

CONTEXT_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
META_FILE = "meta.json"
MEMORY_FILE = "memory.jsonl"
TITLE_MAX_LENGTH = 80


class ChatSessionInfo(pydantic.BaseModel):
    id: str
    agent: str
    title: str | None = None
    created_at: datetime = pydantic.Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = pydantic.Field(default_factory=lambda: datetime.now(UTC))


class ChatSessionNotFound(LookupError):
    pass


class ChatSessionStore:
    """
    Agent chat sessions on disk, one directory per session: `<base_dir>/<context_id>/{meta.json,memory.jsonl}`.

    Only directories with a meta.json are sessions of this store, so other users of the same
    base directory (e.g. the ai_routes chat completion memory) are ignored.

    Each session gets its own agent instance (own memory and HITL controller), cached in an LRU of runners.
    """

    def __init__(
        self,
        base_dir: Path | str,
        agent_registry: AgentRegistry,
        max_runners: int = 32,
        approval_timeout: float = 300,
    ):
        self.base_dir = Path(base_dir)
        self.agent_registry = agent_registry
        self.max_runners = max_runners
        self.approval_timeout = approval_timeout
        self._lock = threading.RLock()
        self._runners: OrderedDict[str, WebAgentRunner] = OrderedDict()

    # -- storage ---------------------------------------------------------------

    def session_dir(self, context_id: str) -> Path:
        """Directory of a session; rejects any context_id that could leave the base directory."""
        if not CONTEXT_ID_RE.fullmatch(context_id or ""):
            raise ValueError(
                "Invalid context_id: expected 1-64 characters of [A-Za-z0-9_-]."
            )
        base = self.base_dir.resolve()
        path = (base / context_id).resolve()
        if path.parent != base:
            raise ValueError("Invalid context_id.")
        return path

    def _write_meta(self, info: ChatSessionInfo) -> None:
        path = self.session_dir(info.id) / META_FILE
        tmp = path.with_suffix(".tmp")
        tmp.write_text(info.model_dump_json(indent=2))
        tmp.replace(path)

    def create(self, agent: str, title: str | None = None) -> ChatSessionInfo:
        if agent not in self.agent_registry.configs:
            raise ValueError(f"Unknown agent '{agent}'.")
        info = ChatSessionInfo(id=uuid.uuid4().hex, agent=agent, title=title)
        with self._lock:
            self.session_dir(info.id).mkdir(parents=True, exist_ok=False)
            self._write_meta(info)
        return info

    def get(self, context_id: str) -> ChatSessionInfo:
        path = self.session_dir(context_id) / META_FILE
        try:
            return ChatSessionInfo.model_validate_json(path.read_text())
        except FileNotFoundError:
            raise ChatSessionNotFound(context_id)

    def list(self) -> list[ChatSessionInfo]:
        if not self.base_dir.is_dir():
            return []
        sessions = []
        for meta in self.base_dir.glob(f"*/{META_FILE}"):
            try:
                sessions.append(ChatSessionInfo.model_validate_json(meta.read_text()))
            except (OSError, pydantic.ValidationError) as e:
                logger.warning(
                    f"Skipping unreadable chat session {meta.parent.name}: {e}"
                )
        return sorted(sessions, key=lambda s: s.updated_at, reverse=True)

    def touch(self, context_id: str, prompt: str | None = None) -> ChatSessionInfo:
        """Update updated_at; the first prompt becomes the title."""
        with self._lock:
            info = self.get(context_id)
            info.updated_at = datetime.now(UTC)
            if not info.title and prompt and prompt.strip():
                title = " ".join(prompt.split())
                info.title = (
                    title
                    if len(title) <= TITLE_MAX_LENGTH
                    else title[: TITLE_MAX_LENGTH - 1] + "…"
                )
            self._write_meta(info)
            return info

    def delete(self, context_id: str) -> None:
        with self._lock:
            self.get(context_id)  # raises if missing
            runner = self._runners.pop(context_id, None)
            if runner:
                runner.cancel()
            shutil.rmtree(self.session_dir(context_id))

    def history(self, context_id: str) -> list[ModelMessage]:
        self.get(context_id)
        with self._lock:
            runner = self._runners.get(context_id)
        if runner:
            return list(runner.agent.message_history)
        return list(
            FileChatMemory(str(self.session_dir(context_id) / MEMORY_FILE)).messages
        )

    # -- runners ---------------------------------------------------------------

    def runner(self, context_id: str) -> WebAgentRunner:
        """The session's runner, creating its agent on first use."""
        info = self.get(context_id)
        with self._lock:
            runner = self._runners.get(context_id)
            if runner:
                self._runners.move_to_end(context_id)
                return runner

            spec = self.agent_registry.get_config(info.agent)
            if spec is None:
                raise ValueError(
                    f"Agent '{info.agent}' of chat {context_id} is no longer configured."
                )
            hitl = WebHumanInTheLoopController(approval_timeout=self.approval_timeout)
            memory = FileChatMemory(str(self.session_dir(context_id) / MEMORY_FILE))
            agent = init_agent(spec, context_id=context_id, memory=memory, hitl=hitl)
            runner = WebAgentRunner(agent, hitl)
            self._runners[context_id] = runner
            self._evict()
            return runner

    def get_runner(self, context_id: str) -> WebAgentRunner | None:
        """The session's runner if it is loaded (no agent is created)."""
        with self._lock:
            return self._runners.get(context_id)

    def _evict(self) -> None:
        # drop the least recently used idle runners; their memory is on disk
        for context_id in list(self._runners):
            if len(self._runners) <= self.max_runners:
                break
            if not self._runners[context_id].busy:
                del self._runners[context_id]
