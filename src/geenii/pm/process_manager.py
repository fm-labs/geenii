"""
Background process manager.

Starts external commands as non-blocking subprocesses, assigns each a short
process ID, and writes stdout/stderr to log files on disk.  Callers can
check process state and read captured output at any time via the process ID.

The manager is asyncio-based: all public methods are coroutines and must run
on the event loop that owns the manager (the ProcessManagerService loop).

Commands are dispatched by type:
    str        – run through the shell (/bin/sh -c), so pipes, redirects,
                 `&&`, `cd` etc. work.  The caller supplies the whole command
                 line; no untrusted data is interpolated here.
    list[str]  – executed directly (no shell); each element is one argument.

Every process is started in its own process group (see geenii.proc) so that
kill() and shutdown() also reach processes spawned by the command.

The child's stdout/stderr are connected directly to the log files, so no
reader tasks are needed and output keeps being written even if the manager
exits unexpectedly.

Output directory layout (under CACHE_DIR/processes/<pid>/):
    meta.json   – process metadata and current state
    stdout.log  – captured standard output
    stderr.log  – captured standard error
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
import signal
import time
import uuid
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from geenii import proc as proc_util
from geenii.config import CACHE_DIR, PM_GC_MAX_AGE

logger = logging.getLogger(__name__)

PROCESSES_DIR = os.path.join(CACHE_DIR, "processes")

KILL_WAIT_S = 5.0        # how long kill() waits for the process to exit before returning
TERMINATE_GRACE_S = proc_util.TERMINATE_GRACE_S  # SIGTERM → SIGKILL grace period used by shutdown()

# Process IDs become directory names: allow only a safe, bounded character set
# (no path separators, no leading dot, so no "." / ".." / hidden files).
_PID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")

# A UTF-8 character is a lead byte followed by at most 3 continuation bytes (0b10xxxxxx)
_UTF8_MAX_CONT = 3


def _is_utf8_cont(byte: int) -> bool:
    return byte & 0xC0 == 0x80


class ProcessState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"
    # The manager exited while the process was running; its final state is unknown.
    ORPHANED = "orphaned"


_ACTIVE_STATES = (ProcessState.PENDING, ProcessState.RUNNING)
# States gc() removes by default. Orphaned processes are left alone: they may still be running.
_GC_STATES = frozenset((ProcessState.COMPLETED, ProcessState.FAILED, ProcessState.KILLED))


def validate_pid(pid: str) -> str:
    """Return pid if it is a valid process ID, else raise ValueError."""
    if not isinstance(pid, str) or not _PID_RE.match(pid):
        raise ValueError(
            f"Invalid process ID {pid!r}: use 1-64 letters, digits, '_' or '-', starting with a letter or digit"
        )
    return pid


@dataclass
class ProcessInfo:
    pid: str
    system_pid: int
    cmd: str | List[str]
    state: ProcessState
    cwd: Optional[str]
    env: Optional[Dict[str, str]]
    started_at: float
    shell: bool = False
    finished_at: Optional[float] = None
    exit_code: Optional[int] = None
    error: Optional[str] = None
    stdout_path: str = ""
    stderr_path: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pid": self.pid,
            "system_pid": self.system_pid,
            "cmd": self.cmd,
            "shell": self.shell,
            "state": self.state.value,
            "cwd": self.cwd,
            "env_keys": sorted(self.env) if self.env else [],
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "exit_code": self.exit_code,
            "error": self.error,
            "stdout_path": self.stdout_path,
            "stderr_path": self.stderr_path,
        }

    @classmethod
    def from_meta(cls, meta: Dict[str, Any]) -> "ProcessInfo":
        return cls(
            pid=meta["pid"],
            system_pid=meta["system_pid"],
            cmd=meta["cmd"],
            state=ProcessState(meta["state"]),
            cwd=meta.get("cwd"),
            env=None,  # values are never persisted
            started_at=meta["started_at"],
            shell=meta.get("shell", isinstance(meta["cmd"], str)),
            finished_at=meta.get("finished_at"),
            exit_code=meta.get("exit_code"),
            error=meta.get("error"),
            stdout_path=meta.get("stdout_path", ""),
            stderr_path=meta.get("stderr_path", ""),
        )


@dataclass
class _RunningProcess:
    info: ProcessInfo
    proc: asyncio.subprocess.Process
    waiter: Optional[asyncio.Task] = None
    kill_requested: bool = False


class ProcessManager:
    """Manage background subprocesses with file-backed output capture (asyncio)."""

    def __init__(self, processes_dir: Optional[str] = None) -> None:
        # Resolved at call time, so the module default can be redirected (e.g. in tests)
        self._processes_dir = processes_dir or PROCESSES_DIR
        self._procs: Dict[str, _RunningProcess] = {}
        # Serializes the check-and-register part of start() across awaits
        self._start_lock = asyncio.Lock()

    def _make_pid(self) -> str:
        return uuid.uuid4().hex[:12]

    def _proc_path(self, pid: str) -> str:
        """Directory for a process. Validates the ID; does not create anything."""
        return os.path.join(self._processes_dir, validate_pid(pid))

    def _write_meta(self, info: ProcessInfo) -> None:
        proc_dir = self._proc_path(info.pid)
        os.makedirs(proc_dir, exist_ok=True)
        meta_path = os.path.join(proc_dir, "meta.json")
        # Write atomically so concurrent readers never see a partial file
        tmp_path = f"{meta_path}.tmp"
        with open(tmp_path, "w") as f:
            json.dump(info.to_dict(), f, indent=2)
        os.replace(tmp_path, meta_path)

    def _read_meta(self, pid: str) -> Optional[Dict[str, Any]]:
        meta_path = os.path.join(self._proc_path(pid), "meta.json")
        if not os.path.isfile(meta_path):
            return None
        with open(meta_path, "r") as f:
            return json.load(f)

    def recover(self) -> List[str]:
        """Mark processes left 'running' on disk by a previous manager instance as orphaned.

        Call once when the owning service starts (the daemon does). Not done in
        __init__: other short-lived instances sharing the directory (e.g. a
        local `geenii scheduler run`) must not touch the daemon's live records.
        Returns the IDs marked as orphaned.
        """
        orphaned: List[str] = []
        if not os.path.isdir(self._processes_dir):
            return orphaned
        for name in os.listdir(self._processes_dir):
            if not _PID_RE.match(name):
                continue
            try:
                meta = self._read_meta(name)
                if meta is None or ProcessState(meta["state"]) not in _ACTIVE_STATES:
                    continue
                info = ProcessInfo.from_meta(meta)
                info.state = ProcessState.ORPHANED
                info.error = "process manager exited while the process was running; final state unknown"
                self._write_meta(info)
                orphaned.append(name)
                logger.warning(f"Marked process {name} (system pid {info.system_pid}) as orphaned")
            except Exception as exc:
                logger.error(f"Could not reconcile process directory {name}: {exc}")
        return orphaned

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    async def start(
        self,
        cmd: str | List[str],
        *,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        pid: Optional[str] = None,
    ) -> ProcessInfo:
        """
        Start a background process.

        :param cmd: Command to run. A string is run through the shell; a list
                    is executed directly without a shell.
        :param env: Extra environment variables (merged into os.environ).
        :param cwd: Working directory for the process.
        :param pid: Explicit process ID. Auto-generated if omitted. Must be
                    unused and match [A-Za-z0-9][A-Za-z0-9_-]{0,63}.
        :return: ProcessInfo with the assigned pid and initial state.
        """
        if isinstance(cmd, str):
            if not cmd.strip():
                raise ValueError("Command must not be empty")
            shell = True
            argv = proc_util.shell_argv(cmd)
        elif isinstance(cmd, list) and cmd and all(isinstance(a, str) for a in cmd):
            shell = False
            argv = cmd
        else:
            raise ValueError("Command must be a non-empty string or a non-empty list of strings")

        async with self._start_lock:
            pid = validate_pid(pid) if pid else self._make_pid()
            proc_dir = self._proc_path(pid)
            if pid in self._procs or os.path.exists(proc_dir):
                raise ValueError(f"Process ID {pid!r} is already in use")

            os.makedirs(proc_dir)
            stdout_path = os.path.join(proc_dir, "stdout.log")
            stderr_path = os.path.join(proc_dir, "stderr.log")
            try:
                # The child gets its own descriptors; ours can be closed right after spawning
                with open(stdout_path, "ab") as out, open(stderr_path, "ab") as err:
                    p = await proc_util.spawn(argv, env=env, cwd=cwd, stdout=out, stderr=err)
            except BaseException:
                shutil.rmtree(proc_dir, ignore_errors=True)
                raise

            info = ProcessInfo(
                pid=pid,
                system_pid=p.pid,
                cmd=cmd,
                state=ProcessState.RUNNING,
                cwd=cwd,
                env=env,
                started_at=time.time(),
                shell=shell,
                stdout_path=stdout_path,
                stderr_path=stderr_path,
            )
            rp = _RunningProcess(info=info, proc=p)
            self._procs[pid] = rp
            self._write_meta(info)
            rp.waiter = asyncio.create_task(self._wait(rp), name=f"pm-wait:{pid}")

        logger.info(f"Started process {pid} (system pid {p.pid}, shell={shell}): {cmd}")
        return info

    async def status(self, pid: str) -> ProcessInfo:
        """Return current state of a process."""
        validate_pid(pid)
        rp = self._procs.get(pid)
        if rp is not None:
            return rp.info

        meta = await asyncio.to_thread(self._read_meta, pid)
        if meta is None:
            raise KeyError(f"Unknown process: {pid}")
        return ProcessInfo.from_meta(meta)

    async def output(
        self,
        pid: str,
        stream: str = "stdout",
        tail: Optional[int] = None,
        *,
        offset: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> str:
        """
        Read captured output of a process.

        Either the last `tail` lines, or a chunk of `limit` bytes starting at
        byte `offset` (tail is mutually exclusive with offset/limit). To read the
        whole output in chunks, advance offset by limit until an empty string is
        returned. A UTF-8 character split across a chunk boundary is returned
        whole with the chunk holding its first byte, so concatenated chunks equal
        the full output (with limit >= 4, a chunk is only empty past the end).

        :param pid: Process ID.
        :param stream: "stdout" or "stderr".
        :param tail: If set, return only the last N lines.
        :param offset: Byte position to start reading at (default 0).
        :param limit: Maximum number of bytes to read (default: to the end).
        :return: The captured output as a string.
        """
        if stream not in ("stdout", "stderr"):
            raise ValueError(f"Invalid stream {stream!r}: must be 'stdout' or 'stderr'")
        if tail is not None and (offset is not None or limit is not None):
            raise ValueError("tail cannot be combined with offset/limit")
        if offset is not None and offset < 0:
            raise ValueError("offset must be >= 0")
        if limit is not None and limit < 1:
            raise ValueError("limit must be >= 1")
        log_file = os.path.join(self._proc_path(pid), f"{stream}.log")
        if tail is not None:
            return await asyncio.to_thread(self._read_log_tail, pid, stream, log_file, tail)
        return await asyncio.to_thread(self._read_log_chunk, pid, stream, log_file, offset or 0, limit)

    async def wait(self, pid: str, timeout: Optional[float] = None) -> ProcessInfo:
        """
        Wait until a process has finished and return its final ProcessInfo.

        Returns immediately for processes that already finished (or are orphaned).
        Cancelling the wait does not affect the process.

        :param timeout: Maximum seconds to wait; raises asyncio.TimeoutError when exceeded.
        """
        validate_pid(pid)
        rp = self._procs.get(pid)
        if rp is not None and rp.waiter is not None:
            await asyncio.wait_for(asyncio.shield(rp.waiter), timeout=timeout)
            return rp.info
        return await self.status(pid)

    async def kill(self, pid: str, *, force: bool = False) -> ProcessInfo:
        """
        Kill a running process and its process group.

        Waits up to KILL_WAIT_S for the process to exit, so the returned
        state is final unless the process ignores SIGTERM.

        :param pid: Process ID.
        :param force: If True, send SIGKILL instead of SIGTERM.
        :return: Updated ProcessInfo.
        """
        validate_pid(pid)
        rp = self._procs.get(pid)
        if rp is None:
            raise KeyError(f"Process {pid} is not running (may have already finished)")

        sig = proc_util.SIGKILL if force else signal.SIGTERM
        rp.kill_requested = True
        proc_util.signal_group(rp.proc, sig)
        logger.info(f"Sent {signal.Signals(sig).name} to process {pid} (process group {rp.proc.pid})")

        if rp.waiter:
            try:
                await asyncio.wait_for(asyncio.shield(rp.waiter), timeout=KILL_WAIT_S)
            except asyncio.TimeoutError:
                pass
        return rp.info

    async def list(self, *, include_finished: bool = False) -> List[ProcessInfo]:
        """
        List tracked processes.

        :param include_finished: If True, also scan disk for finished processes
                                 that are no longer in memory.
        """
        by_pid: Dict[str, ProcessInfo] = {pid: rp.info for pid, rp in self._procs.items()}
        if include_finished:
            # A process may finish while the scan runs; keep the in-memory entry then
            for info in await asyncio.to_thread(self._scan_finished, set(by_pid)):
                by_pid.setdefault(info.pid, info)
        return sorted(by_pid.values(), key=lambda i: i.started_at, reverse=True)

    async def cleanup(self, pid: str) -> None:
        """Remove all on-disk artifacts for a finished process."""
        proc_dir = self._proc_path(pid)
        if pid in self._procs:
            raise RuntimeError(f"Process {pid} is still tracked in memory; wait for it to finish or kill it first")

        if os.path.isdir(proc_dir):
            await asyncio.to_thread(shutil.rmtree, proc_dir)
            logger.info(f"Cleaned up process directory: {proc_dir}")

    async def gc(
        self,
        max_age: Optional[float] = None,
        *,
        states: Optional[List[str]] = None,
        dry_run: bool = False,
    ) -> List[str]:
        """
        Remove the on-disk artifacts of processes that finished long enough ago.

        :param max_age: Minimum seconds since a process finished (default: PM_GC_MAX_AGE).
        :param states: States to collect (default: completed, failed, killed).
                       Pending/running processes are never collected.
        :param dry_run: Only report what would be removed.
        :return: IDs of the removed (or, with dry_run, removable) processes, oldest first.
        """
        max_age = PM_GC_MAX_AGE if max_age is None else max_age
        if max_age < 0:
            raise ValueError("max_age must be >= 0")
        gc_states = frozenset(ProcessState(s) for s in states) if states else _GC_STATES
        if gc_states & set(_ACTIVE_STATES):
            raise ValueError("Pending or running processes cannot be garbage collected")
        removed = await asyncio.to_thread(
            self._gc, time.time() - max_age, gc_states, set(self._procs), dry_run)
        if removed and not dry_run:
            logger.info(f"Garbage collected {len(removed)} process(es) finished more than {max_age:g}s ago")
        return removed

    async def shutdown(self) -> None:
        """Terminate all running processes (SIGTERM, then SIGKILL) and record their final state.

        Called when the owning service stops, so no process is left untracked.
        """
        running = list(self._procs.values())
        for rp in running:
            rp.kill_requested = True
        await asyncio.gather(
            *(proc_util.terminate(rp.proc, grace=TERMINATE_GRACE_S) for rp in running),
            return_exceptions=True,
        )
        await asyncio.gather(*(rp.waiter for rp in running if rp.waiter), return_exceptions=True)
        if running:
            logger.info(f"Terminated {len(running)} running process(es) on shutdown")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _wait(self, rp: _RunningProcess) -> None:
        """Wait for a process to exit, then update state and persist metadata."""
        rc = await rp.proc.wait()

        info = rp.info
        info.finished_at = time.time()
        info.exit_code = rc

        if rc == 0:
            info.state = ProcessState.COMPLETED
        elif rc < 0 or rp.kill_requested:
            info.state = ProcessState.KILLED
        else:
            info.state = ProcessState.FAILED

        try:
            self._write_meta(info)
        except OSError as exc:
            logger.error(f"Could not persist final state of process {info.pid}: {exc}")
        finally:
            self._procs.pop(info.pid, None)
        logger.info(f"Process {info.pid} finished: state={info.state.value} exit_code={info.exit_code}")

    @staticmethod
    def _read_log_tail(pid: str, stream: str, log_file: str, tail: int) -> str:
        if not os.path.isfile(log_file):
            raise KeyError(f"No {stream} log for process {pid}")
        with open(log_file, "r", errors="replace") as f:
            return "".join(deque(f, maxlen=max(tail, 0))).rstrip("\n")

    @staticmethod
    def _read_log_chunk(pid: str, stream: str, log_file: str, offset: int, limit: Optional[int]) -> str:
        if not os.path.isfile(log_file):
            raise KeyError(f"No {stream} log for process {pid}")
        with open(log_file, "rb") as f:
            f.seek(offset)
            data = f.read() if limit is None else f.read(limit)
            if not data:
                return ""
            # A character belongs to the chunk holding its first byte: skip the
            # continuation bytes the previous chunk already returned, and complete
            # a character cut off at the end of this one.
            start = 0
            if offset > 0:
                while start < min(_UTF8_MAX_CONT, len(data)) and _is_utf8_cont(data[start]):
                    start += 1
            if limit is not None:
                extra = f.read(_UTF8_MAX_CONT)
                end = 0
                while end < len(extra) and _is_utf8_cont(extra[end]):
                    end += 1
                data += extra[:end]
        return data[start:].decode("utf-8", errors="replace")

    def _gc(self, cutoff: float, states: frozenset, known_pids: set[str], dry_run: bool) -> List[str]:
        candidates = []
        # A directory without meta.json may belong to a process being started: skip it
        for info in self._scan_finished(known_pids):
            finished = info.finished_at or info.started_at
            if info.state in states and finished < cutoff:
                candidates.append((finished, info.pid))
        removed = []
        for _, pid in sorted(candidates):
            if not dry_run:
                try:
                    shutil.rmtree(self._proc_path(pid))
                except OSError as exc:
                    logger.error(f"Could not remove process directory of {pid}: {exc}")
                    continue
            removed.append(pid)
        return removed

    def _scan_finished(self, known_pids: set[str]) -> List[ProcessInfo]:
        if not os.path.isdir(self._processes_dir):
            return []
        found = []
        for name in os.listdir(self._processes_dir):
            if name in known_pids or not _PID_RE.match(name):
                continue
            meta = self._read_meta(name)
            if meta is not None:
                found.append(ProcessInfo.from_meta(meta))
        return found
