import os
import queue
import shlex
import subprocess
import threading
import time
from collections.abc import Generator
from typing import IO, Any

import pydantic

from geenii.flow.flow import FlowContext, FlowProcessor, StepEvent, register_processor


class ExecuteCommandConfig(pydantic.BaseModel):
    command: str | list[str]
    shell: bool = False
    cwd: str | None = None
    env: dict[str, str] | None = None
    stdin: str | None = None
    timeout: float | None = None
    check: bool = False


class ExecuteCommandOutput(pydantic.BaseModel):
    stdout: str
    stderr: str
    rc: int


def run_process(
    args: str | list[str],
    shell: bool = False,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    stdin: str | None = None,
    timeout: float | None = None,
    check: bool = False,
) -> Generator[StepEvent, None, ExecuteCommandOutput]:
    """
    Run a process to completion. env is merged over the current environment.

    Yields a "stdout" or "stderr" event for each line of output while the
    process runs (without the line ending), and returns the collected output.
    """
    proc = subprocess.Popen(
        args,
        shell=shell,
        cwd=cwd,
        env={**os.environ, **env} if env else None,
        stdin=subprocess.PIPE if stdin is not None else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    lines: queue.Queue[tuple[str, str | None]] = queue.Queue()

    def read(name: str, pipe: IO[str]):
        with pipe:
            for line in iter(pipe.readline, ""):
                lines.put((name, line))
        lines.put((name, None))

    def write(pipe: IO[str], text: str):
        with pipe:
            try:
                pipe.write(text)
            except BrokenPipeError:
                pass

    threads = [
        threading.Thread(target=read, args=("stdout", proc.stdout), daemon=True),
        threading.Thread(target=read, args=("stderr", proc.stderr), daemon=True),
    ]
    if stdin is not None:
        threads.append(
            threading.Thread(target=write, args=(proc.stdin, stdin), daemon=True)
        )
    for t in threads:
        t.start()

    deadline = time.monotonic() + timeout if timeout is not None else None
    collected: dict[str, list[str]] = {"stdout": [], "stderr": []}
    open_streams = 2
    try:
        while open_streams:
            remaining = deadline - time.monotonic() if deadline is not None else None
            try:
                name, line = lines.get(
                    timeout=max(remaining, 0) if remaining is not None else None
                )
            except queue.Empty:
                raise subprocess.TimeoutExpired(args, timeout) from None
            if line is None:
                open_streams -= 1
                continue
            collected[name].append(line)
            yield StepEvent(name, line.rstrip("\r\n"))
        remaining = deadline - time.monotonic() if deadline is not None else None
        rc = proc.wait(timeout=max(remaining, 0) if remaining is not None else None)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()

    stdout, stderr = "".join(collected["stdout"]), "".join(collected["stderr"])
    if check and rc != 0:
        raise RuntimeError(f"Command exited with code {rc}: {stderr.strip()}")
    return ExecuteCommandOutput(stdout=stdout, stderr=stderr, rc=rc)


@register_processor("execute_command")
class ExecuteCommandProcessor(FlowProcessor):
    """Runs a command in a subprocess"""

    config_model = ExecuteCommandConfig
    output_model = ExecuteCommandOutput

    def process(
        self, input_data: Any, ctx: FlowContext
    ) -> Generator[Any, None, ExecuteCommandOutput]:
        c: ExecuteCommandConfig = self.config
        if c.shell:
            args = c.command if isinstance(c.command, str) else shlex.join(c.command)
        else:
            args = shlex.split(c.command) if isinstance(c.command, str) else c.command
        yield StepEvent("log", f"Running {args!r}")
        return (
            yield from run_process(
                args,
                shell=c.shell,
                cwd=c.cwd,
                env=c.env,
                stdin=c.stdin,
                timeout=c.timeout,
                check=c.check,
            )
        )
