"""Background discovery of MCP server tools.

Starting an MCP server can take a long time (e.g. when its docker image has to be pulled first), so the
API server does not wait for it at startup. The loader discovers each server's tools on a thread pool and
shares one discovery per server among all callers: the startup preload, agents that need the server, and
reloads after a config change. Registries attached to the loader get each server's tools as soon as they
are discovered.
"""

from __future__ import annotations

import dataclasses
import logging
import threading
import time
from collections.abc import Callable, Iterable
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from enum import Enum

from geenii import config
from geenii import tools as tools_mod
from geenii.mcp_config import get_mcp_config
from geenii.tool.registry import ToolRegistry

logger = logging.getLogger(__name__)


class McpLoadState(str, Enum):
    PENDING = "pending"  # not requested yet
    QUEUED = "queued"  # requested, waiting for a free worker
    LOADING = "loading"
    READY = "ready"
    FAILED = "failed"


@dataclasses.dataclass
class McpServerStatus:
    name: str
    state: McpLoadState = McpLoadState.PENDING
    tool_count: int = 0
    error: str | None = None
    attempts: int = 0
    started_at: float | None = None
    finished_at: float | None = None
    # bumped on every new discovery, so that results of a superseded one are ignored
    generation: int = 0

    def to_dict(self) -> dict:
        d = dataclasses.asdict(self)
        d["state"] = self.state.value
        del d["generation"]
        return d


class McpToolLoader:
    def __init__(
        self,
        discover: Callable[[str], list[dict]] | None = None,
        max_workers: int | None = None,
        retry_cooldown: float | None = None,
    ):
        """
        :param discover: lists a server's tools, raising on failure. Default: the cached `read_mcp_server_tools`.
        :param max_workers: number of servers discovered at the same time.
        :param retry_cooldown: seconds before a failed server is tried again when its tools are requested.
        """
        self._discover = discover
        self._retry_cooldown = config.MCP_RETRY_COOLDOWN if retry_cooldown is None else retry_cooldown
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers or config.MCP_LOAD_CONCURRENCY,
            thread_name_prefix="mcp-loader",
        )
        self._lock = threading.RLock()
        self._futures: dict[str, Future] = {}
        self._status: dict[str, McpServerStatus] = {}
        self._registries: list[ToolRegistry] = []
        self._closed = False

    @property
    def discover(self) -> Callable[[str], list[dict]]:
        # resolved on use, so that a patched `read_mcp_server_tools` is picked up
        return self._discover or tools_mod.read_mcp_server_tools

    # -- loading --------------------------------------------------------------

    def ensure(self, name: str, *, force: bool = False) -> Future:
        """The discovery of a server's tools, started if it isn't running or done yet.

        A failed discovery is started again once the retry cooldown has passed. `force` always starts a new one.
        """
        with self._lock:
            if self._closed:
                raise RuntimeError("MCP tool loader is shut down")
            fut = self._futures.get(name)
            if fut is not None and not force and not self._should_retry(name, fut):
                return fut

            status = self._status.setdefault(name, McpServerStatus(name))
            status.generation += 1
            status.state = McpLoadState.QUEUED
            gen = status.generation
            fut = self._executor.submit(self._run, name, gen)
            self._futures[name] = fut
            fut.add_done_callback(lambda f: self._on_done(name, gen, f))
            return fut

    def _should_retry(self, name: str, fut: Future) -> bool:
        if not fut.done() or (not fut.cancelled() and fut.exception() is None):
            return False
        finished_at = self._status[name].finished_at or 0
        return time.time() - finished_at >= self._retry_cooldown

    def start(self, names: Iterable[str] | None = None) -> None:
        """Start discovering the given servers (default: all configured) without waiting for them."""
        for name in self._resolve(names):
            self.ensure(name)

    def reload(self, name: str) -> Future:
        """Discover a server's tools again, bypassing the cache, e.g. after its config changed."""
        self._invalidate(name)
        return self.ensure(name, force=True)

    def forget(self, name: str) -> None:
        """Drop a server, e.g. after it was removed from the config. Its tools are removed from attached registries."""
        self._invalidate(name)
        with self._lock:
            self._futures.pop(name, None)
            self._status.pop(name, None)
            for registry in self._registries:
                registry.unregister_mcp_tools(name)

    def _invalidate(self, name: str) -> None:
        invalidate = getattr(self.discover, "invalidate", None)
        if invalidate is not None:
            try:
                invalidate(name)
            except Exception as e:
                logger.warning(f"Could not drop cached tools of MCP server '{name}': {e}")

    def _run(self, name: str, gen: int) -> list[dict]:
        with self._lock:
            status = self._status.get(name)
            if status is not None and status.generation == gen:
                status.state = McpLoadState.LOADING
                status.started_at = time.time()
                status.attempts += 1
        logger.info(f"Discovering tools of MCP server '{name}'")
        return self.discover(name)

    def _on_done(self, name: str, gen: int, fut: Future) -> None:
        with self._lock:
            status = self._status.get(name)
            if status is None or status.generation != gen:
                return  # superseded by a reload, or forgotten

            status.finished_at = time.time()
            tools = None
            if fut.cancelled():
                status.state = McpLoadState.FAILED
                status.error = "cancelled"
            elif fut.exception() is not None:
                status.state = McpLoadState.FAILED
                status.error = str(fut.exception()) or type(fut.exception()).__name__
                logger.error(f"Failed to discover tools of MCP server '{name}': {status.error}")
            else:
                tools = fut.result()
                status.state = McpLoadState.READY
                status.error = None
                status.tool_count = len(tools)
                logger.info(f"Discovered {len(tools)} tools of MCP server '{name}'")

            # replace the server's tools: a reload may have changed them, and a failed one leaves none
            for registry in self._registries:
                self._register(registry, name, tools)

    @staticmethod
    def _register(registry: ToolRegistry, name: str, tools: list[dict] | None) -> None:
        registry.unregister_mcp_tools(name)
        if tools:
            registry.register_mcp_tools(mcp_server_id=name, tool_definitions=tools)

    # -- registries -----------------------------------------------------------

    def attach(self, registry: ToolRegistry) -> None:
        """Keep a registry up to date with the tools of all servers, as each one is discovered."""
        with self._lock:
            if registry in self._registries:
                return
            self._registries.append(registry)
            for name, fut in self._futures.items():
                if fut.done() and not fut.cancelled() and fut.exception() is None:
                    self._register(registry, name, fut.result())

    def detach(self, registry: ToolRegistry) -> None:
        with self._lock:
            if registry in self._registries:
                self._registries.remove(registry)

    def register_into(
        self,
        registry: ToolRegistry,
        names: Iterable[str] | None = None,
        timeout: float | None = None,
    ) -> None:
        """Register the tools of the given servers (default: all configured), waiting for their discovery.

        A server that fails, or is not loaded within `timeout` seconds overall, is skipped with a warning.
        """
        futures = {name: self.ensure(name) for name in self._resolve(names)}
        deadline = None if timeout is None else time.monotonic() + timeout
        for name, fut in futures.items():
            remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
            try:
                tools = fut.result(timeout=remaining)
            except FutureTimeoutError:
                logger.warning(f"MCP server '{name}' is still loading after {timeout}s; continuing without its tools")
                continue
            except (Exception, CancelledError) as e:
                logger.error(f"MCP server '{name}' is not available, continuing without its tools: {e}")
                continue
            if tools:
                registry.register_mcp_tools(mcp_server_id=name, tool_definitions=tools)

    # -- status ---------------------------------------------------------------

    def status(self, name: str | None = None) -> list[dict]:
        """Load status of the configured servers (or of one), including servers not loaded yet."""
        names = self._resolve([name] if name is not None else None, warn=False)
        with self._lock:
            return [(self._status.get(n) or McpServerStatus(n)).to_dict() for n in names]

    def _resolve(self, names: Iterable[str] | None, warn: bool = True) -> list[str]:
        """The configured servers among `names` (default: all)."""
        configured = list(get_mcp_config().get("mcpServers", {}))
        if names is None:
            return configured
        resolved = []
        for name in names:
            if name in configured:
                resolved.append(name)
            elif warn:
                logger.warning(f"MCP server '{name}' is not configured")
        return resolved

    # -- lifecycle ------------------------------------------------------------

    def shutdown(self) -> None:
        """Stop the loader. Queued discoveries are cancelled; running ones finish in their threads."""
        with self._lock:
            self._closed = True
            self._registries.clear()
        self._executor.shutdown(wait=False, cancel_futures=True)


_loader: McpToolLoader | None = None
_loader_lock = threading.Lock()


def get_mcp_loader() -> McpToolLoader:
    """The process-wide loader, shared by the server, agents and the CLI."""
    global _loader
    with _loader_lock:
        if _loader is None:
            _loader = McpToolLoader()
        return _loader


def shutdown_mcp_loader() -> None:
    global _loader
    with _loader_lock:
        loader, _loader = _loader, None
    if loader is not None:
        loader.shutdown()
