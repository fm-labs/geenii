"""
Background process manager.

Starts external commands as non-blocking subprocesses, assigns each a short
process ID, and streams stdout/stderr to log files on disk.  Callers can
check process state and read captured output at any time via the process ID.

Commands are dispatched by type:
    str        – run through the shell (/bin/sh -c), so pipes, redirects,
                 `&&`, `cd` etc. work.  The caller supplies the whole command
                 line; no untrusted data is interpolated here.
    list[str]  – executed directly (no shell); each element is one argument.

Every process is started in its own process group so that kill() and
shutdown() also reach processes spawned by the command (e.g. by the shell).

Output directory layout (under CACHE_DIR/processes/<pid>/):
    meta.json   – process metadata and current state
    stdout.log  – captured standard output
    stderr.log  – captured standard error
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import signal
import subprocess
import threading
import time
import uuid
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from geenii.config import CACHE_DIR

logger = logging.getLogger(__name__)

PROCESSES_DIR = os.path.join(CACHE_DIR, "processes")

KILL_WAIT_S = 5.0        # how long kill() waits for the process to exit before returning
TERMINATE_GRACE_S = 5.0  # SIGTERM → SIGKILL grace period used by shutdown()

# Process IDs become directory names: allow only a safe, bounded character set
# (no path separators, no leading dot, so no "." / ".." / hidden files).
_PID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$")


class ProcessState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"
    # The manager exited while the process was running; its fate is unknown
    # and its output is no longer captured.
    ORPHANED = "orphaned"


_ACTIVE_STATES = (ProcessState.PENDING, ProcessState.RUNNING)


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
    proc: subprocess.Popen
    stdout_thread: Optional[threading.Thread] = None
    stderr_thread: Optional[threading.Thread] = None
    waiter: Optional[threading.Thread] = None
    kill_requested: bool = False


class ProcessManager:
    """Manage background subprocesses with file-backed output capture."""

    def __init__(self, processes_dir: str = PROCESSES_DIR) -> None:
        self._processes_dir = processes_dir
        self._procs: Dict[str, _RunningProcess] = {}
        self._lock = threading.Lock()
        self._reconcile_orphans()

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

    def _reconcile_orphans(self) -> None:
        """Mark processes left 'running' on disk by a previous manager instance as orphaned."""
        if not os.path.isdir(self._processes_dir):
            return
        for name in os.listdir(self._processes_dir):
            if not _PID_RE.match(name):
                continue
            try:
                meta = self._read_meta(name)
                if meta is None or ProcessState(meta["state"]) not in _ACTIVE_STATES:
                    continue
                info = ProcessInfo.from_meta(meta)
                info.state = ProcessState.ORPHANED
                info.error = "process manager exited while the process was running"
                self._write_meta(info)
                logger.warning(f"Marked process {name} (system pid {info.system_pid}) as orphaned")
            except Exception as exc:
                logger.error(f"Could not reconcile process directory {name}: {exc}")

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------

    def start(
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
        elif isinstance(cmd, list) and cmd and all(isinstance(a, str) for a in cmd):
            shell = False
        else:
            raise ValueError("Command must be a non-empty string or a non-empty list of strings")

        with self._lock:
            pid = validate_pid(pid) if pid else self._make_pid()
            proc_dir = self._proc_path(pid)
            if pid in self._procs or os.path.exists(proc_dir):
                raise ValueError(f"Process ID {pid!r} is already in use")

            merged_env = os.environ.copy()
            if env:
                merged_env.update(env)

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=merged_env,
                cwd=cwd,
                shell=shell,
                start_new_session=True,  # own process group, see kill()
            )

            os.makedirs(proc_dir)
            info = ProcessInfo(
                pid=pid,
                system_pid=proc.pid,
                cmd=cmd,
                state=ProcessState.RUNNING,
                cwd=cwd,
                env=env,
                started_at=time.time(),
                shell=shell,
                stdout_path=os.path.join(proc_dir, "stdout.log"),
                stderr_path=os.path.join(proc_dir, "stderr.log"),
            )
            rp = _RunningProcess(info=info, proc=proc)
            self._procs[pid] = rp
            self._write_meta(info)

        rp.stdout_thread = threading.Thread(
            target=self._drain, args=(pid, proc.stdout, info.stdout_path), daemon=True
        )
        rp.stderr_thread = threading.Thread(
            target=self._drain, args=(pid, proc.stderr, info.stderr_path), daemon=True
        )
        rp.waiter = threading.Thread(target=self._wait, args=(rp,), daemon=True)
        rp.stdout_thread.start()
        rp.stderr_thread.start()
        rp.waiter.start()

        logger.info(f"Started process {pid} (system pid {proc.pid}, shell={shell}): {cmd}")
        return info

    def status(self, pid: str) -> ProcessInfo:
        """Return current state of a process."""
        validate_pid(pid)
        with self._lock:
            rp = self._procs.get(pid)
        if rp is not None:
            return rp.info

        meta = self._read_meta(pid)
        if meta is None:
            raise KeyError(f"Unknown process: {pid}")
        return ProcessInfo.from_meta(meta)

    def output(self, pid: str, stream: str = "stdout", tail: Optional[int] = None) -> str:
        """
        Read captured output of a process.

        :param pid: Process ID.
        :param stream: "stdout" or "stderr".
        :param tail: If set, return only the last N lines.
        :return: The captured output as a string.
        """
        if stream not in ("stdout", "stderr"):
            raise ValueError(f"Invalid stream {stream!r}: must be 'stdout' or 'stderr'")
        log_file = os.path.join(self._proc_path(pid), f"{stream}.log")
        if not os.path.isfile(log_file):
            raise KeyError(f"No {stream} log for process {pid}")
        with open(log_file, "r", errors="replace") as f:
            if tail is None:
                return f.read()
            return "".join(deque(f, maxlen=max(tail, 0))).rstrip("\n")

    def kill(self, pid: str, *, force: bool = False) -> ProcessInfo:
        """
        Kill a running process and its process group.

        Waits up to KILL_WAIT_S for the process to exit, so the returned
        state is final unless the process ignores SIGTERM.

        :param pid: Process ID.
        :param force: If True, send SIGKILL instead of SIGTERM.
        :return: Updated ProcessInfo.
        """
        validate_pid(pid)
        with self._lock:
            rp = self._procs.get(pid)
        if rp is None:
            raise KeyError(f"Process {pid} is not running (may have already finished)")

        sig = signal.SIGKILL if force else signal.SIGTERM
        rp.kill_requested = True
        self._signal_group(rp, sig)
        logger.info(f"Sent {sig.name} to process {pid} (process group {rp.proc.pid})")

        if rp.waiter:
            rp.waiter.join(timeout=KILL_WAIT_S)
        return rp.info

    def list(self, *, include_finished: bool = False) -> List[ProcessInfo]:
        """
        List tracked processes.

        :param include_finished: If True, also scan disk for finished processes
                                 that are no longer in memory.
        """
        result: List[ProcessInfo] = []

        with self._lock:
            for rp in self._procs.values():
                result.append(rp.info)

        if include_finished and os.path.isdir(self._processes_dir):
            known_pids = {info.pid for info in result}
            for name in os.listdir(self._processes_dir):
                if name in known_pids or not _PID_RE.match(name):
                    continue
                meta = self._read_meta(name)
                if meta is not None:
                    result.append(ProcessInfo.from_meta(meta))

        result.sort(key=lambda i: i.started_at, reverse=True)
        return result

    def cleanup(self, pid: str) -> None:
        """Remove all on-disk artifacts for a finished process."""
        proc_dir = self._proc_path(pid)
        with self._lock:
            if pid in self._procs:
                raise RuntimeError(f"Process {pid} is still tracked in memory; wait for it to finish or kill it first")

        if os.path.isdir(proc_dir):
            shutil.rmtree(proc_dir)
            logger.info(f"Cleaned up process directory: {proc_dir}")

    def shutdown(self) -> None:
        """Terminate all running processes (SIGTERM, then SIGKILL) and record their final state.

        Called when the owning service stops: without it, output could no
        longer be captured and the processes would be left untracked.
        """
        with self._lock:
            running = list(self._procs.values())
        for rp in running:
            rp.kill_requested = True
            self._signal_group(rp, signal.SIGTERM)
        deadline = time.time() + TERMINATE_GRACE_S
        for rp in running:
            if rp.waiter:
                rp.waiter.join(timeout=max(0.0, deadline - time.time()))
        for rp in running:
            if rp.proc.poll() is None:
                self._signal_group(rp, signal.SIGKILL)
            if rp.waiter:
                rp.waiter.join(timeout=TERMINATE_GRACE_S)
        if running:
            logger.info(f"Terminated {len(running)} running process(es) on shutdown")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _signal_group(rp: _RunningProcess, sig: int) -> None:
        # start_new_session=True makes the child a group leader: pgid == pid.
        # Signalling the group also reaches children the command spawned.
        try:
            os.killpg(rp.proc.pid, sig)
        except ProcessLookupError:
            pass

    def _drain(self, pid: str, pipe, log_path: str) -> None:
        """Read lines from a pipe and append them to a log file."""
        try:
            with open(log_path, "ab") as f:
                for line in iter(pipe.readline, b""):
                    f.write(line)
                    f.flush()
        except Exception as exc:
            logger.error(f"Drain error for {pid}: {exc}")
        finally:
            pipe.close()

    def _wait(self, rp: _RunningProcess) -> None:
        """Wait for a process to exit, then update state and persist metadata."""
        rp.proc.wait()

        # Pipes stay open while other members of the group hold them; don't block forever
        if rp.stdout_thread:
            rp.stdout_thread.join(timeout=5)
        if rp.stderr_thread:
            rp.stderr_thread.join(timeout=5)

        info = rp.info
        info.finished_at = time.time()
        info.exit_code = rp.proc.returncode

        if rp.proc.returncode == 0:
            info.state = ProcessState.COMPLETED
        elif rp.proc.returncode < 0 or rp.kill_requested:
            info.state = ProcessState.KILLED
        else:
            info.state = ProcessState.FAILED

        with self._lock:
            self._write_meta(info)
            self._procs.pop(info.pid, None)
        logger.info(f"Process {info.pid} finished: state={info.state.value} exit_code={info.exit_code}")
