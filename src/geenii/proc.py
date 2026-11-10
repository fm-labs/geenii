"""
Shared subprocess helpers for the process-management components
(Supervisor, Scheduler, ProcessManager).

Conventions shared by all helpers:

- Environment: extra variables are merged over ``os.environ``, never replace it.
- Process groups: every child is started in its own session / process group
  (``start_new_session=True``), so signals reach everything the command
  spawned — e.g. the members of ``sh -c "a | b"`` or backgrounded jobs —
  not just the direct child.  On platforms without ``os.killpg`` the helpers
  fall back to signalling the child alone.
- Termination: SIGTERM to the group, wait up to a grace period, then SIGKILL.
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
from typing import IO, Callable, Mapping, Optional, Sequence, Union

USE_PROCESS_GROUPS = hasattr(os, "killpg")
SIGKILL = getattr(signal, "SIGKILL", signal.SIGTERM)
TERMINATE_GRACE_S = 5.0
STREAM_LINE_LIMIT = 1024 * 1024  # max length of a single output line for async readers

AnyProcess = Union[asyncio.subprocess.Process, subprocess.Popen]


def merged_env(extra: Optional[Mapping[str, str]] = None) -> dict[str, str]:
    """Return a copy of os.environ with extra variables applied on top."""
    env = os.environ.copy()
    if extra:
        env.update(extra)
    return env


def signal_group(proc: AnyProcess, sig: int) -> None:
    """Send sig to the process group led by proc (or to proc alone without process groups).

    proc must have been started with start_new_session=True (as spawn() does),
    otherwise the group signal would hit the caller's own group.  A process
    that has already exited is ignored.
    """
    try:
        if USE_PROCESS_GROUPS:
            os.killpg(proc.pid, sig)
        else:
            proc.send_signal(sig)
    except ProcessLookupError:
        pass


async def spawn(
    cmd: Sequence[str],
    *,
    env: Optional[Mapping[str, str]] = None,
    cwd: Optional[str] = None,
    capture_output: bool = True,
    stdout: Optional[IO] = None,
    stderr: Optional[IO] = None,
    limit: int = STREAM_LINE_LIMIT,
) -> asyncio.subprocess.Process:
    """Start cmd (an argument vector, no shell) in its own process group.

    :param env: Extra environment variables, merged over os.environ.
    :param capture_output: Pipe stdout/stderr (read them with pump_lines());
                           otherwise the child inherits the caller's streams.
    :param stdout: Explicit target for stdout (e.g. an open log file); overrides capture_output.
    :param stderr: Explicit target for stderr; overrides capture_output.
    :param limit: Maximum line length for the stream readers.
    """
    pipe = asyncio.subprocess.PIPE if capture_output else None
    return await asyncio.create_subprocess_exec(
        *cmd,
        stdout=stdout if stdout is not None else pipe,
        stderr=stderr if stderr is not None else pipe,
        env=merged_env(env),
        cwd=cwd,
        start_new_session=USE_PROCESS_GROUPS,
        limit=limit,
    )


async def terminate(
    proc: asyncio.subprocess.Process, grace: float = TERMINATE_GRACE_S
) -> Optional[int]:
    """Terminate proc's process group: SIGTERM, wait up to grace seconds, then SIGKILL.

    Returns the exit code.  A process that has already exited is left alone.
    Note: asyncio's proc.wait() also waits for the output pipes to close, so
    stop reading them (or let pump_lines() finish) before relying on a prompt return.
    """
    if proc.returncode is not None:
        return proc.returncode
    signal_group(proc, signal.SIGTERM)
    try:
        return await asyncio.wait_for(proc.wait(), timeout=grace)
    except asyncio.TimeoutError:
        signal_group(proc, SIGKILL)
        return await proc.wait()


def shell_argv(command: str) -> list[str]:
    """Argument vector that runs command through /bin/sh, like subprocess's shell=True on POSIX."""
    return ["/bin/sh", "-c", command]


def terminate_sync(
    proc: subprocess.Popen, grace: float = TERMINATE_GRACE_S
) -> Optional[int]:
    """Blocking variant of terminate() for subprocess.Popen (start it with start_new_session=True)."""
    if proc.poll() is not None:
        return proc.returncode
    signal_group(proc, signal.SIGTERM)
    try:
        return proc.wait(timeout=grace)
    except subprocess.TimeoutExpired:
        signal_group(proc, SIGKILL)
        return proc.wait()


async def pump_lines(
    stream: asyncio.StreamReader, on_line: Callable[[str], None]
) -> None:
    """Read stream until EOF, calling on_line with each decoded line (trailing whitespace stripped)."""
    while True:
        line = await stream.readline()
        if not line:
            return
        on_line(line.decode(errors="replace").rstrip())


def add_shutdown_handlers(
    on_signal: Callable[[], object],
    loop: Optional[asyncio.AbstractEventLoop] = None,
    signals: Sequence[int] = (signal.SIGINT, signal.SIGTERM),
) -> None:
    """Call on_signal (a plain callable, run in the loop) when the process receives SIGINT/SIGTERM.

    For async shutdown work pass e.g. ``lambda: asyncio.create_task(shutdown())``.
    Must be called from the thread running the loop.
    """
    loop = loop or asyncio.get_running_loop()
    for sig in signals:
        loop.add_signal_handler(sig, on_signal)
