import os
import shlex
import subprocess
from typing import Any, Generator

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


def run_process(args: str | list[str], shell: bool = False, cwd: str | None = None,
                env: dict[str, str] | None = None, stdin: str | None = None,
                timeout: float | None = None, check: bool = False) -> ExecuteCommandOutput:
    """Run a process to completion. env is merged over the current environment."""
    proc = subprocess.run(
        args,
        shell=shell,
        cwd=cwd,
        env={**os.environ, **env} if env else None,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"Command exited with code {proc.returncode}: {proc.stderr.strip()}")
    return ExecuteCommandOutput(stdout=proc.stdout, stderr=proc.stderr, rc=proc.returncode)


@register_processor("execute_command")
class ExecuteCommandProcessor(FlowProcessor):
    """Runs a command in a subprocess"""

    config_model = ExecuteCommandConfig
    output_model = ExecuteCommandOutput

    def process(self, input_data: Any, ctx: FlowContext) -> Generator[Any, None, ExecuteCommandOutput]:
        c: ExecuteCommandConfig = self.config
        if c.shell:
            args = c.command if isinstance(c.command, str) else shlex.join(c.command)
        else:
            args = shlex.split(c.command) if isinstance(c.command, str) else c.command
        yield StepEvent("log", f"Running {args!r}")
        return run_process(args, shell=c.shell, cwd=c.cwd, env=c.env, stdin=c.stdin,
                           timeout=c.timeout, check=c.check)
