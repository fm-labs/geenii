"""
Process supervisor
"""

import asyncio
import json
import os
import signal
import uuid
import time
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Dict, List, Literal, Optional


# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

@dataclass
class ProcConfig:
    name: str
    cmd: List[str]
    restart: bool = True
    env: Optional[Dict[str, str]] = None   # extra vars; merged into os.environ at spawn time
    cwd: Optional[str] = None
    capture_output: bool = True


@dataclass
class ProcRuntime:
    proc: asyncio.subprocess.Process
    started_at: float = field(default_factory=time.time)
    last_exit: Optional[Dict[str, Any]] = None
    # Backoff lives here and accumulates across restarts; reset only on a
    # clean exit (returncode == 0) or on an explicit restart call.
    backoff: float = 3
    out_task: Optional[asyncio.Task] = None
    err_task: Optional[asyncio.Task] = None

@dataclass
class RunResult:
    returncode: int
    stdout: List[str]   # lines, no trailing newline
    stderr: List[str]
    duration_s: float

# ---------------------------------------------------------------------------
# Log bus: per-process ring buffer + async subscriber queues for streaming
# ---------------------------------------------------------------------------

Tag = Literal["stdout", "stderr", "supervisor"]


@dataclass
class LogEvent:
    t: float          # unix timestamp
    name: str         # process name
    tag: Tag          # origin
    msg: str          # log line (no trailing newline)

    def as_text(self) -> str:
        """Plain-text representation used by the existing string stream."""
        return f"[{self.tag}] {self.msg}"

    def as_json(self) -> str:
        """Compact JSON line (no trailing newline)."""
        return json.dumps({"t": self.t, "name": self.name, "tag": self.tag, "msg": self.msg}, separators=(",", ":"))


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
            q.put_nowait(event)

    def subscribe(self) -> "asyncio.Queue[LogEvent]":
        q: asyncio.Queue[LogEvent] = asyncio.Queue()
        self._subs.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        try:
            self._subs.remove(q)
        except ValueError:
            pass

    def tail_text(self, n: int) -> List[str]:
        return [e.as_text() for e in self._buf[-max(1, n):]]

    def tail_events(self, n: int) -> List[LogEvent]:
        return list(self._buf[-max(1, n):])

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

    def is_active(self) -> bool:
        # True if a process is running or any watcher tasks are active; used for graceful shutdowns
        return bool(self._runtime) or any(not t.done() for t in self._watchers.values()) or not self._stop_event.is_set()


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

        merged_env = {**os.environ}
        if env:
            merged_env.update(env)

        self._logs.setdefault(job, LogBus())
        self._log(job, f"starting: {' '.join(cmd)}")
        t0 = time.time()

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=merged_env,
            cwd=cwd,
        )

        stdout_lines: List[str] = []
        stderr_lines: List[str] = []

        async def drain(stream: asyncio.StreamReader, tag: Tag, buf: List[str]) -> None:
            while True:
                line = await stream.readline()
                if not line:
                    return
                text = line.decode(errors="replace").rstrip()
                buf.append(text)
                self._emit(job, tag, text)

        try:
            await asyncio.wait_for(
                asyncio.gather(
                    drain(proc.stdout, "stdout", stdout_lines),
                    drain(proc.stderr, "stderr", stderr_lines),
                    proc.wait(),
                ),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.wait()
            self._log(job, f"killed after {timeout}s timeout")
            raise

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
            watcher = self._watchers.pop(name, None)
            if watcher:
                watcher.cancel()
                await asyncio.gather(watcher, return_exceptions=True)
            await self._terminate_locked(name)

    async def restart_process(self, name: str) -> None:
        async with self._lock:
            if name not in self._configs:
                raise KeyError(name)
            # Terminate; watcher will respawn.  Reset backoff on explicit restart.
            rt = self._runtime.get(name)
            if rt:
                rt.backoff = 0.5
            await self._terminate_locked(name)
            self._ensure_watcher_locked(name)

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
                "backoff_s": rt.backoff,
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

                # Backoff: only escalate on non-zero exits; reset on clean exit
                backoff = rt.backoff
                if rc != 0:
                    rt.backoff = min(backoff * 2, 30.0)
                else:
                    rt.backoff = 0.5

                self._runtime.pop(name, None)
                self._log(name, f"restarting in {backoff:.1f}s")
                try:
                    await asyncio.sleep(backoff)
                except asyncio.CancelledError:
                    raise

            else:
                # Not running yet (or runtime cleared) — spawn it.
                try:
                    await self._spawn(name, cfg)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self._log(name, f"spawn error: {type(exc).__name__}: {exc}")
                    await asyncio.sleep(1.0)

    async def _spawn(self, name: str, cfg: ProcConfig) -> None:
        self._log(name, f"starting: {' '.join(cfg.cmd)}")

        # Merge extra env vars into current environment (not a replacement)
        merged_env = {**os.environ}
        if cfg.env:
            merged_env.update(cfg.env)

        stdout = asyncio.subprocess.PIPE if cfg.capture_output else None
        stderr = asyncio.subprocess.PIPE if cfg.capture_output else None

        proc = await asyncio.create_subprocess_exec(
            *cfg.cmd,
            stdout=stdout,
            stderr=stderr,
            env=merged_env,
            cwd=cfg.cwd,
        )

        # Preserve accumulated backoff if an entry exists (from a previous exit
        # that hasn't been cleaned up yet — shouldn't happen, but be safe)
        prev = self._runtime.get(name)
        backoff = prev.backoff if prev else 0.5

        rt = ProcRuntime(proc=proc, backoff=backoff)
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
            while True:
                line = await stream.readline()
                if not line:
                    return
                self._emit(name, tag, line.decode(errors="replace").rstrip())
        except asyncio.CancelledError:
            return

    def _log(self, name: str, msg: str) -> None:
        """Emit a supervisor-internal log line."""
        self._emit(name, "supervisor", msg)

    def _emit(self, name: str, tag: Tag, msg: str) -> None:
        print(f"[{name}][{tag}] {msg}")
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

        try:
            proc.terminate()
        except ProcessLookupError:
            self._runtime.pop(name, None)
            return

        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.wait()

        self._log(name, f"terminated rc={proc.returncode}")
        self._runtime.pop(name, None)


if __name__ == "__main__":

    supervisor = Supervisor()

    # attach signal handlers for graceful shutdown
    def _shutdown_handler():
        print("Received shutdown signal, stopping supervisor...")
        asyncio.create_task(supervisor.stop())

    #loop = asyncio.get_event_loop()
    #for sig in (signal.SIGINT, signal.SIGTERM):
    #    loop.add_signal_handler(sig, _shutdown_handler)

    async def main():
        # Example 1: ensure a process and print status every 10 seconds
        await supervisor.ensure("example", ProcConfig(name="example", cmd=["/bin/bash", "-c", "while true; do echo `date`; sleep 2; done"]))
        # Example 2: one-shot process that exits immediately
        await supervisor.ensure("oneshot", ProcConfig(name="oneshot", cmd=["/bin/bash", "-c", "echo one-shot; exit 0"], restart=False))

        i = 0
        while supervisor.is_active():
            i += 1
            print(json.dumps(supervisor.status(), indent=2))
            await asyncio.sleep(3)
            if i == 3:
                print("Restarting example process...")
                await supervisor.restart_process("example")
            if i == 6:
                print("Stopping example process...")
                await supervisor.stop_process("example")
            if i == 9:
                print("Stopping supervisor...")
                await supervisor.stop()

    asyncio.run(main())
