"""
Background process manager.

Starts external commands as non-blocking subprocesses, assigns each a short
process ID, and streams stdout/stderr to log files on disk.  Callers can
check process state and read captured output at any time via the process ID.

Output directory layout (under CACHE_DIR/processes/<pid>/):
    meta.json   – process metadata and current state
    stdout.log  – captured standard output
    stderr.log  – captured standard error
"""
from __future__ import annotations

import json
import logging
import os
import shlex
import signal
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from geenii.config import CACHE_DIR

logger = logging.getLogger(__name__)

PROCESSES_DIR = os.path.join(CACHE_DIR, "processes")


class ProcessState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"


@dataclass
class ProcessInfo:
    pid: str
    system_pid: int
    cmd: List[str]
    state: ProcessState
    cwd: Optional[str]
    env: Optional[Dict[str, str]]
    started_at: float
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


@dataclass
class _RunningProcess:
    info: ProcessInfo
    proc: subprocess.Popen
    stdout_thread: Optional[threading.Thread] = None
    stderr_thread: Optional[threading.Thread] = None


class ProcessManager:
    """Manage background subprocesses with file-backed output capture."""

    def __init__(self, processes_dir: str = PROCESSES_DIR) -> None:
        self._processes_dir = processes_dir
        self._procs: Dict[str, _RunningProcess] = {}
        self._lock = threading.Lock()

    def _make_pid(self) -> str:
        return uuid.uuid4().hex[:12]

    def _proc_dir(self, pid: str) -> str:
        d = os.path.join(self._processes_dir, pid)
        os.makedirs(d, exist_ok=True)
        return d

    def _write_meta(self, info: ProcessInfo) -> None:
        meta_path = os.path.join(self._proc_dir(info.pid), "meta.json")
        with open(meta_path, "w") as f:
            json.dump(info.to_dict(), f, indent=2)

    def _read_meta(self, pid: str) -> Optional[Dict[str, Any]]:
        meta_path = os.path.join(self._proc_dir(pid), "meta.json")
        if not os.path.isfile(meta_path):
            return None
        with open(meta_path, "r") as f:
            return json.load(f)

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

        :param cmd: Command to run. A string is split with shlex; a list is
                    used directly.
        :param env: Extra environment variables (merged into os.environ).
        :param cwd: Working directory for the process.
        :param pid: Explicit process ID. Auto-generated if omitted.
        :return: ProcessInfo with the assigned pid and initial state.
        """
        #if isinstance(cmd, str):
        #    cmd = shlex.split(cmd)

        pid = pid or self._make_pid()
        proc_dir = self._proc_dir(pid)
        stdout_path = os.path.join(proc_dir, "stdout.log")
        stderr_path = os.path.join(proc_dir, "stderr.log")

        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=merged_env,
            cwd=cwd,
            shell=True,
        )

        info = ProcessInfo(
            pid=pid,
            system_pid=proc.pid,
            cmd=cmd,
            state=ProcessState.RUNNING,
            cwd=cwd,
            env=env,
            started_at=time.time(),
            stdout_path=stdout_path,
            stderr_path=stderr_path,
        )

        rp = _RunningProcess(info=info, proc=proc)

        rp.stdout_thread = threading.Thread(
            target=self._drain, args=(pid, proc.stdout, stdout_path), daemon=True
        )
        rp.stderr_thread = threading.Thread(
            target=self._drain, args=(pid, proc.stderr, stderr_path), daemon=True
        )
        rp.stdout_thread.start()
        rp.stderr_thread.start()

        with self._lock:
            self._procs[pid] = rp

        self._write_meta(info)

        waiter = threading.Thread(target=self._wait, args=(pid,), daemon=True)
        waiter.start()
        logger.info(f"Started process {pid} (system pid {proc.pid}): {cmd}")
        return info

    def status(self, pid: str) -> ProcessInfo:
        """Return current state of a process."""
        with self._lock:
            rp = self._procs.get(pid)
        if rp is not None:
            return rp.info

        meta = self._read_meta(pid)
        if meta is None:
            raise KeyError(f"Unknown process: {pid}")
        return ProcessInfo(
            pid=meta["pid"],
            system_pid=meta["system_pid"],
            cmd=meta["cmd"],
            state=ProcessState(meta["state"]),
            cwd=meta.get("cwd"),
            env=None,
            started_at=meta["started_at"],
            finished_at=meta.get("finished_at"),
            exit_code=meta.get("exit_code"),
            error=meta.get("error"),
            stdout_path=meta.get("stdout_path", ""),
            stderr_path=meta.get("stderr_path", ""),
        )

    def output(self, pid: str, stream: str = "stdout", tail: Optional[int] = None) -> str:
        """
        Read captured output of a process.

        :param pid: Process ID.
        :param stream: "stdout" or "stderr".
        :param tail: If set, return only the last N lines.
        :return: The captured output as a string.
        """
        proc_dir = os.path.join(self._processes_dir, pid)
        log_file = os.path.join(proc_dir, f"{stream}.log")
        if not os.path.isfile(log_file):
            raise KeyError(f"No {stream} log for process {pid}")
        with open(log_file, "r") as f:
            content = f.read()
        if tail is not None:
            lines = content.splitlines()
            content = "\n".join(lines[-tail:])
        return content

    def kill(self, pid: str, *, force: bool = False) -> ProcessInfo:
        """
        Kill a running process.

        :param pid: Process ID.
        :param force: If True, send SIGKILL instead of SIGTERM.
        :return: Updated ProcessInfo.
        """
        with self._lock:
            rp = self._procs.get(pid)
        if rp is None:
            raise KeyError(f"Process {pid} is not running (may have already finished)")

        sig = signal.SIGKILL if force else signal.SIGTERM
        try:
            rp.proc.send_signal(sig)
            logger.info(f"Sent {sig.name} to process {pid} (system pid {rp.proc.pid})")
        except ProcessLookupError:
            pass

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
                if name in known_pids:
                    continue
                meta = self._read_meta(name)
                if meta is not None:
                    result.append(ProcessInfo(
                        pid=meta["pid"],
                        system_pid=meta["system_pid"],
                        cmd=meta["cmd"],
                        state=ProcessState(meta["state"]),
                        cwd=meta.get("cwd"),
                        env=None,
                        started_at=meta["started_at"],
                        finished_at=meta.get("finished_at"),
                        exit_code=meta.get("exit_code"),
                        error=meta.get("error"),
                        stdout_path=meta.get("stdout_path", ""),
                        stderr_path=meta.get("stderr_path", ""),
                    ))

        result.sort(key=lambda i: i.started_at, reverse=True)
        return result

    def cleanup(self, pid: str) -> None:
        """Remove all on-disk artifacts for a finished process."""
        with self._lock:
            if pid in self._procs:
                raise RuntimeError(f"Process {pid} is still tracked in memory; wait for it to finish or kill it first")

        import shutil
        proc_dir = os.path.join(self._processes_dir, pid)
        if os.path.isdir(proc_dir):
            shutil.rmtree(proc_dir)
            logger.info(f"Cleaned up process directory: {proc_dir}")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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

    def _wait(self, pid: str) -> None:
        """Wait for a process to exit, then update state and persist metadata."""
        with self._lock:
            rp = self._procs.get(pid)
        if rp is None:
            return

        rp.proc.wait()

        if rp.stdout_thread:
            rp.stdout_thread.join(timeout=5)
        if rp.stderr_thread:
            rp.stderr_thread.join(timeout=5)

        info = rp.info
        info.finished_at = time.time()
        info.exit_code = rp.proc.returncode

        if rp.proc.returncode == 0:
            info.state = ProcessState.COMPLETED
        elif rp.proc.returncode < 0:
            info.state = ProcessState.KILLED
        else:
            info.state = ProcessState.FAILED

        self._write_meta(info)
        logger.info(f"Process {pid} finished: state={info.state.value} exit_code={info.exit_code}")

        with self._lock:
            self._procs.pop(pid, None)
