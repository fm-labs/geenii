"""
Process supervisor.

Services can be declared in a JSON file (services.json), which the geenii
daemon applies at startup and on reload:

    {
        "services": [
            {
                "name": "web",
                "cmd": ["python", "-m", "http.server", "8000"],
                "restart": true,
                "env": {"PYTHONUNBUFFERED": "1"},
                "cwd": "~/site",
                "enabled": true
            }
        ]
    }
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
import uuid
from collections import deque
from dataclasses import dataclass, field, replace
from functools import partial
from pathlib import Path
from typing import Any, AsyncIterator, Dict, List, Literal, Optional

import pydantic

from geenii import proc as proc_util

logger = logging.getLogger(__name__)

BACKOFF_INITIAL = 0.5  # restart delay after a clean exit / first crash
BACKOFF_MAX = 30.0  # upper bound for the exponential restart delay
BACKOFF_RESET_AFTER = 60.0  # a process that ran this long counts as healthy again
RUN_LOG_HISTORY = 50  # number of finished one-shot run() log buffers to keep
SUBSCRIBER_QUEUE_SIZE = 1000  # per-subscriber queue bound; oldest events are dropped
TERMINATE_GRACE_S = (
    proc_util.TERMINATE_GRACE_S
)  # SIGTERM → SIGKILL grace period when terminating

# Children are spawned via geenii.proc: each in its own process group, so
# signals reach everything the command spawned, not just the direct child.

# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------


@dataclass
class ProcConfig:
    name: str
    cmd: List[str]
    restart: bool = True
    env: Optional[Dict[str, str]] = (
        None  # extra vars; merged into os.environ at spawn time
    )
    cwd: Optional[str] = None
    capture_output: bool = True


class ServiceConfig(pydantic.BaseModel):
    """One entry of a services config file."""

    model_config = {"extra": "allow"}

    name: str = pydantic.Field(min_length=1)
    cmd: List[str] = pydantic.Field(min_length=1)
    restart: bool = True
    env: Optional[Dict[str, str]] = None
    cwd: Optional[str] = None
    capture_output: bool = True
    enabled: bool = True


def read_services(config_path: str | Path) -> List[ProcConfig]:
    """Parse the enabled services of a services config file.

    `$VAR` in cmd and cwd is expanded from the daemon's environment, and `~`
    in cwd. Invalid entries, disabled services and duplicate names are logged
    and skipped. Raises FileNotFoundError / ValueError for a missing or
    unparsable file.
    """
    config_path = Path(config_path)
    data = json.loads(config_path.read_text())
    if not isinstance(data, dict):
        raise ValueError(
            f"{config_path}: expected a JSON object with a 'services' list"
        )

    services: List[ProcConfig] = []
    names: set[str] = set()
    for entry in data.get("services", []):
        try:
            conf = ServiceConfig.model_validate(entry)
        except pydantic.ValidationError as e:
            logger.error(
                "Invalid service in %s: %s — skipping entry: %s", config_path, e, entry
            )
            continue
        if not conf.enabled:
            logger.info("Service '%s' is disabled — skipping", conf.name)
            continue
        if conf.name in names:
            logger.error(
                "Duplicate service name '%s' in %s — skipping", conf.name, config_path
            )
            continue
        names.add(conf.name)
        services.append(
            ProcConfig(
                name=conf.name,
                cmd=[os.path.expandvars(arg) for arg in conf.cmd],
                restart=conf.restart,
                env=conf.env,
                cwd=os.path.expanduser(os.path.expandvars(conf.cwd))
                if conf.cwd
                else None,
                capture_output=conf.capture_output,
            )
        )
    return services


class UpdateProcRequest(pydantic.BaseModel):
    restart: Optional[bool] = None
    env: Optional[Dict[str, str]] = None
    cwd: Optional[str] = None


@dataclass
class ProcRuntime:
    proc: asyncio.subprocess.Process
    started_at: float = field(default_factory=time.time)
    last_exit: Optional[Dict[str, Any]] = None
    out_task: Optional[asyncio.Task] = None
    err_task: Optional[asyncio.Task] = None


@dataclass
class RunResult:
    returncode: int
    stdout: List[str]  # lines, no trailing newline
    stderr: List[str]
    duration_s: float


# ---------------------------------------------------------------------------
# Log bus: per-process ring buffer + async subscriber queues for streaming
# ---------------------------------------------------------------------------

Tag = Literal["stdout", "stderr", "supervisor"]


@dataclass
class LogEvent:
    t: float  # unix timestamp
    name: str  # process name
    tag: Tag  # origin
    msg: str  # log line (no trailing newline)

    def as_text(self) -> str:
        """Plain-text representation used by the existing string stream."""
        return f"[{self.tag}] {self.msg}"

    def as_json(self) -> str:
        """Compact JSON line (no trailing newline)."""
        return json.dumps(
            {"t": self.t, "name": self.name, "tag": self.tag, "msg": self.msg},
            separators=(",", ":"),
        )


class LogBus:
    """
    Asyncio-safe ring buffer of LogEvents with fan-out to live subscribers.
    """

    def __init__(self, maxlines: int = 400) -> None:
        self._maxlines = maxlines
        self._buf: List[LogEvent] = []
        self._subs: List[asyncio.Queue] = []

    def append(self, event: LogEvent) -> None:
        self._buf.append(event)
        if len(self._buf) > self._maxlines:
            del self._buf[: len(self._buf) - self._maxlines]
        for q in self._subs:
            if q.full():
                # Slow subscriber: drop its oldest event instead of growing unbounded
                q.get_nowait()
            q.put_nowait(event)

    def subscribe(self) -> "asyncio.Queue[LogEvent]":
        q: asyncio.Queue[LogEvent] = asyncio.Queue(maxsize=SUBSCRIBER_QUEUE_SIZE)
        self._subs.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        try:
            self._subs.remove(q)
        except ValueError:
            pass

    def tail_text(self, n: int) -> List[str]:
        return [e.as_text() for e in self._buf[-max(1, n) :]]

    def tail_events(self, n: int) -> List[LogEvent]:
        return list(self._buf[-max(1, n) :])


# ---------------------------------------------------------------------------
# Supervisor
# ---------------------------------------------------------------------------


class Supervisor:
    """
    Desired-state process supervisor.

    Public API methods are safe to call from concurrent FastAPI handlers.
    Internal watcher tasks run in the same asyncio event loop and communicate
    via the lock for config changes and direct asyncio coordination for process
    lifecycle.
    """

    def __init__(self) -> None:
        self._stop_event = asyncio.Event()
        self._lock = asyncio.Lock()

        self._configs: Dict[str, ProcConfig] = {}
        self._runtime: Dict[str, ProcRuntime] = {}
        self._watchers: Dict[str, asyncio.Task] = {}
        self._logs: Dict[str, LogBus] = {}
        # Restart delay per process. Kept outside ProcRuntime because the
        # runtime entry is dropped on every exit.
        self._backoff: Dict[str, float] = {}
        # Names of finished one-shot run() jobs, oldest first; evicted ones lose their LogBus
        self._run_history: deque[str] = deque()
        # Services declared in the config file, as last applied (copies; see apply_services)
        self._configured: Dict[str, ProcConfig] = {}

    def is_active(self) -> bool:
        # True if a process is running or any watcher tasks are active; used for graceful shutdowns
        return bool(self._runtime) or any(not t.done() for t in self._watchers.values())

    # ------------------------------------------------------------------
    # One-shot command runner (useful for ad-hoc tasks, not part of the desired-state model)
    # ------------------------------------------------------------------

    async def run(
        self,
        cmd: List[str],
        *,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        timeout: Optional[float] = None,
        name: Optional[str] = None,  # visible in status/logs; auto-generated if omitted
    ) -> RunResult:
        """
        Spawn a one-shot command, wait for it to finish, return its output.
        The process is registered in the supervisor's log bus so its output
        is visible via the normal logs/stream endpoints while it runs.
        Raises asyncio.TimeoutError if timeout is exceeded (process is killed).
        """
        job = name or f"run-{uuid.uuid4().hex[:8]}"

        self._logs.setdefault(job, LogBus())
        self._log(job, f"starting: {' '.join(cmd)}")
        t0 = time.time()

        try:
            proc = await proc_util.spawn(cmd, env=env, cwd=cwd)
        except Exception as exc:
            self._log(job, f"spawn error: {type(exc).__name__}: {exc}")
            self._retire_run_log(job)
            raise

        stdout_lines: List[str] = []
        stderr_lines: List[str] = []

        def collect(tag: Tag, buf: List[str], text: str) -> None:
            buf.append(text)
            self._emit(job, tag, text)

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    proc_util.pump_lines(
                        proc.stdout, partial(collect, "stdout", stdout_lines)
                    ),
                    proc_util.pump_lines(
                        proc.stderr, partial(collect, "stderr", stderr_lines)
                    ),
                    proc.wait(),
                ),
                timeout=timeout,
            )
        except BaseException as exc:
            # Timeout or cancellation by the caller — don't leave the command running
            proc_util.signal_group(proc, proc_util.SIGKILL)
            await proc.wait()
            if isinstance(exc, asyncio.TimeoutError):
                self._log(job, f"killed after {timeout}s timeout")
            else:
                self._log(job, f"killed: {type(exc).__name__}")
            raise
        finally:
            self._retire_run_log(job)

        rc = proc.returncode
        self._log(job, f"exited rc={rc} in {time.time() - t0:.2f}s")

        return RunResult(
            returncode=rc,
            stdout=stdout_lines,
            stderr=stderr_lines,
            duration_s=round(time.time() - t0, 3),
        )

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def stop(self) -> None:
        self._stop_event.set()
        async with self._lock:
            for t in list(self._watchers.values()):
                t.cancel()
            await asyncio.gather(*self._watchers.values(), return_exceptions=True)
            self._watchers.clear()

            await asyncio.gather(
                *(self._terminate_locked(name) for name in list(self._runtime)),
                return_exceptions=True,
            )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def ensure(self, name: str, cfg: ProcConfig) -> None:
        """Register/replace config and ensure a watcher is running."""
        async with self._lock:
            self._configs[name] = cfg
            self._logs.setdefault(name, LogBus())
            self._ensure_watcher_locked(name)

    async def stop_process(self, name: str, *, disable_restart: bool = True) -> None:
        async with self._lock:
            if disable_restart:
                self._configs.pop(name, None)
                self._backoff.pop(name, None)
            await self._cancel_watcher_locked(name)
            await self._terminate_locked(name)

    async def restart_process(self, name: str) -> None:
        async with self._lock:
            if name not in self._configs:
                raise KeyError(name)
            # Replace the watcher rather than relying on it to respawn: with
            # restart=False the old watcher would just exit after termination.
            await self._cancel_watcher_locked(name)
            await self._terminate_locked(name)
            self._backoff[name] = BACKOFF_INITIAL
            self._ensure_watcher_locked(name)

    async def apply_services(self, services: List[ProcConfig]) -> Dict[str, List[str]]:
        """Make the config-file services match `services` (the file's current content).

        - new services, and file services not currently desired (e.g. stopped
          via the API), are started;
        - services removed from the file are stopped;
        - services whose definition changed are updated and restarted now.
        Services added through the API (ensure) and not in the file are untouched.
        """
        new = {c.name: c for c in services}
        old = self._configured
        started, stopped, restarted = [], [], []

        for name in sorted(set(old) - set(new)):
            await self.stop_process(name, disable_restart=True)
            stopped.append(name)

        for name, cfg in new.items():
            if name not in self._configs:
                await self.ensure(name, replace(cfg))
                started.append(name)
            elif name not in old or old[name] != cfg:
                # Changed in the file (or an API-defined service now declared in the file)
                await self.ensure(name, replace(cfg))
                await self.restart_process(name)
                restarted.append(name)

        # Snapshot copies: ensure() stores its own object, which update_config() mutates
        self._configured = {name: replace(cfg) for name, cfg in new.items()}
        changes = {
            "started": sorted(started),
            "stopped": stopped,
            "restarted": sorted(restarted),
        }
        logger.info("Applied services config: %s", changes)
        return changes

    async def update_config(self, name: str, req: "UpdateProcRequest") -> None:
        async with self._lock:
            cfg = self._configs.get(name)
            if cfg is None:
                raise KeyError(name)
            if req.restart is not None:
                cfg.restart = req.restart
            # Only touch env/cwd if the caller explicitly included the field
            if "env" in req.model_fields_set:
                cfg.env = req.env  # None clears it; dict updates it
            if "cwd" in req.model_fields_set:
                cfg.cwd = req.cwd

    def status(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"desired": {}, "running": {}, "watchers": {}}
        for name, cfg in self._configs.items():
            out["desired"][name] = {
                "source": "config" if name in self._configured else "api",
                "cmd": cfg.cmd,
                "restart": cfg.restart,
                "cwd": cfg.cwd,
                "capture_output": cfg.capture_output,
                "env_keys": sorted(cfg.env) if cfg.env else [],
            }
        for name, rt in self._runtime.items():
            out["running"][name] = {
                "pid": rt.proc.pid,
                "returncode": rt.proc.returncode,
                "uptime_s": round(time.time() - rt.started_at, 3),
                "backoff_s": self._backoff.get(name, BACKOFF_INITIAL),
                "last_exit": rt.last_exit,
            }
        for name, t in self._watchers.items():
            out["watchers"][name] = {
                "done": t.done(),
                "cancelled": t.cancelled(),
                "task_name": t.get_name(),
            }
        return out

    def logs(self, name: str, tail: int = 100) -> List[str]:
        bus = self._logs.get(name)
        if bus is None:
            raise KeyError(name)
        return bus.tail_text(tail)

    async def stream_logs(self, name: str) -> AsyncIterator[str]:
        """Yield plain-text log lines as they arrive (SSE-friendly)."""
        bus = self._logs.get(name)
        if bus is None:
            raise KeyError(name)
        q = bus.subscribe()
        try:
            for event in bus.tail_events(bus._maxlines):
                yield event.as_text()
            while not self._stop_event.is_set():
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15)
                    yield event.as_text()
                except asyncio.TimeoutError:
                    yield ""  # keepalive sentinel; route converts to SSE comment
        finally:
            bus.unsubscribe(q)

    async def stream_logs_jsonl(self, name: str) -> AsyncIterator[LogEvent]:
        """Yield LogEvents as they arrive (for JSONL SSE endpoint)."""
        bus = self._logs.get(name)
        if bus is None:
            raise KeyError(name)
        q = bus.subscribe()
        try:
            for event in bus.tail_events(bus._maxlines):
                yield event
            while not self._stop_event.is_set():
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15)
                    yield event
                except asyncio.TimeoutError:
                    yield None  # type: ignore[misc]  # keepalive sentinel
        finally:
            bus.unsubscribe(q)

    # ------------------------------------------------------------------
    # Internals — must be called with _lock held (where noted)
    # ------------------------------------------------------------------

    def _ensure_watcher_locked(self, name: str) -> None:
        t = self._watchers.get(name)
        if t is None or t.done():
            self._watchers[name] = asyncio.create_task(
                self._watch(name), name=f"watch:{name}"
            )

    async def _cancel_watcher_locked(self, name: str) -> None:
        watcher = self._watchers.pop(name, None)
        if watcher:
            watcher.cancel()
            await asyncio.gather(watcher, return_exceptions=True)

    def _next_delay(self, name: str, rc: Optional[int], uptime: float) -> float:
        """Return how long to wait before respawning, and update the stored backoff.

        Clean exits and processes that stayed up for BACKOFF_RESET_AFTER seconds
        restart quickly; repeated failures double the delay up to BACKOFF_MAX.
        """
        if rc == 0 or uptime >= BACKOFF_RESET_AFTER:
            self._backoff[name] = BACKOFF_INITIAL
        delay = self._backoff.get(name, BACKOFF_INITIAL)
        if rc != 0:
            self._backoff[name] = min(delay * 2, BACKOFF_MAX)
        return delay

    def _retire_run_log(self, job: str) -> None:
        """Keep the LogBus of a finished run() job, evicting the oldest beyond RUN_LOG_HISTORY."""
        try:
            self._run_history.remove(job)
        except ValueError:
            pass
        self._run_history.append(job)
        while len(self._run_history) > RUN_LOG_HISTORY:
            old = self._run_history.popleft()
            # Never drop the log bus of a supervised process that shares the name
            if old not in self._configs:
                self._logs.pop(old, None)

    async def _watch(self, name: str) -> None:
        """
        Desired-state loop.  Runs outside any lock; acquires it only when
        mutating shared dicts (config read is effectively immutable once set).
        """
        while not self._stop_event.is_set():
            # Read config without lock — single-threaded asyncio means this
            # is consistent as long as we don't yield between check and use
            # for invariant-sensitive operations (those go through the lock).
            cfg = self._configs.get(name)
            if cfg is None:
                return

            rt = self._runtime.get(name)
            if rt is not None and rt.proc.returncode is None:
                # Process is running; wait for it to exit.
                try:
                    rc = await rt.proc.wait()
                except asyncio.CancelledError:
                    await self._terminate_one(name)
                    raise

                rt.last_exit = {"returncode": rc, "exited_at": time.time()}
                self._log(name, f"exited rc={rc}")

                # Re-read config after await — it may have changed
                cfg = self._configs.get(name)
                if self._stop_event.is_set() or cfg is None or not cfg.restart:
                    self._runtime.pop(name, None)
                    return

                delay = self._next_delay(name, rc, time.time() - rt.started_at)
                self._runtime.pop(name, None)
                self._log(name, f"restarting in {delay:.1f}s")
                await asyncio.sleep(delay)

            else:
                # Not running yet (or runtime cleared) — spawn it.
                try:
                    await self._spawn(name, cfg)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    # Escalate the same backoff as crashes to avoid tight loops
                    delay = self._next_delay(name, None, 0.0)
                    self._log(
                        name,
                        f"spawn error: {type(exc).__name__}: {exc}. retrying in {delay:.1f}s",
                    )
                    await asyncio.sleep(delay)

    async def _spawn(self, name: str, cfg: ProcConfig) -> None:
        self._log(name, f"starting: {' '.join(cfg.cmd)}")

        # cfg.env is merged over os.environ (not a replacement)
        proc = await proc_util.spawn(
            cfg.cmd, env=cfg.env, cwd=cfg.cwd, capture_output=cfg.capture_output
        )

        rt = ProcRuntime(proc=proc)
        self._runtime[name] = rt

        if cfg.capture_output:
            if proc.stdout is not None:
                rt.out_task = asyncio.create_task(
                    self._pipe(name, proc.stdout, "stdout"), name=f"pipe:{name}:out"
                )
            if proc.stderr is not None:
                rt.err_task = asyncio.create_task(
                    self._pipe(name, proc.stderr, "stderr"), name=f"pipe:{name}:err"
                )

        self._log(name, f"started pid={proc.pid}")

    async def _pipe(self, name: str, stream: asyncio.StreamReader, tag: Tag) -> None:
        try:
            await proc_util.pump_lines(stream, partial(self._emit, name, tag))
        except asyncio.CancelledError:
            return

    def _log(self, name: str, msg: str) -> None:
        """Emit a supervisor-internal log line."""
        self._emit(name, "supervisor", msg)

    def _emit(self, name: str, tag: Tag, msg: str) -> None:
        logger.info(f"[{name}][{tag}] {msg}")
        event = LogEvent(t=time.time(), name=name, tag=tag, msg=msg)
        self._logs.setdefault(name, LogBus()).append(event)

    async def _terminate_locked(self, name: str) -> None:
        """Terminate a process. Caller must hold _lock."""
        if not self._lock.locked():
            raise RuntimeError("_terminate_locked must be called with _lock held")
        await self._terminate_one(name)

    async def _terminate_one(self, name: str) -> None:
        """Terminate a process. May be called with or without the lock."""
        rt = self._runtime.get(name)
        if rt is None:
            return

        # Cancel log pipes
        for t in (rt.out_task, rt.err_task):
            if t:
                t.cancel()
        await asyncio.gather(
            *(t for t in (rt.out_task, rt.err_task) if t), return_exceptions=True
        )

        proc = rt.proc
        if proc.returncode is not None:
            self._runtime.pop(name, None)
            return

        await proc_util.terminate(proc, grace=TERMINATE_GRACE_S)
        self._log(name, f"terminated rc={proc.returncode}")
        self._runtime.pop(name, None)


# if __name__ == "__main__":
#
#     supervisor = Supervisor()
#
#     # attach signal handlers for graceful shutdown
#     def _shutdown_handler():
#         print("Received shutdown signal, stopping supervisor...")
#         asyncio.create_task(supervisor.stop())
#
#     #loop = asyncio.get_event_loop()
#     #for sig in (signal.SIGINT, signal.SIGTERM):
#     #    loop.add_signal_handler(sig, _shutdown_handler)
#
#     async def main():
#         # Example 1: ensure a process and print status every 10 seconds
#         await supervisor.ensure("example", ProcConfig(name="example", cmd=["/bin/bash", "-c", "while true; do echo `date`; sleep 2; done"]))
#         # Example 2: one-shot process that exits immediately
#         await supervisor.ensure("oneshot", ProcConfig(name="oneshot", cmd=["/bin/bash", "-c", "echo one-shot; exit 0"], restart=False))
#
#         i = 0
#         while supervisor.is_active():
#             i += 1
#             print(json.dumps(supervisor.status(), indent=2))
#             await asyncio.sleep(3)
#             if i == 3:
#                 print("Restarting example process...")
#                 await supervisor.restart_process("example")
#             if i == 6:
#                 print("Stopping example process...")
#                 await supervisor.stop_process("example")
#             if i == 9:
#                 print("Stopping supervisor...")
#                 await supervisor.stop()
#
#     asyncio.run(main())
