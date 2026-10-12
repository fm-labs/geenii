import json
import sys
import textwrap
from typing import Any, Generator

import pydantic

from geenii.flow.flow import FlowContext, FlowProcessor, StepEvent, register_processor
from geenii.flow.processor.execute_command import run_process


class ExecuteScriptConfig(pydantic.BaseModel):
    script: str
    args: list[str] = []
    cwd: str | None = None
    env: dict[str, str] | None = None
    timeout: float | None = None
    check: bool = True
    json_output: bool = False


class ExecuteScriptOutput(pydantic.BaseModel):
    stdout: str
    stderr: str
    rc: int
    result: Any = None


@register_processor("execute_script")
class ExecuteScriptProcessor(FlowProcessor):
    """
    Runs a Python script in a separate interpreter process.

    The step input is passed as JSON on stdin. With json_output, stdout is
    parsed as JSON into `result`.
    """

    config_model = ExecuteScriptConfig
    output_model = ExecuteScriptOutput

    def process(self, input_data: Any, ctx: FlowContext) -> Generator[Any, None, ExecuteScriptOutput]:
        c: ExecuteScriptConfig = self.config
        yield StepEvent("log", "Running script")
        out = run_process(
            [sys.executable, "-c", textwrap.dedent(c.script), *c.args],
            cwd=c.cwd, env=c.env, stdin=json.dumps(input_data, default=str),
            timeout=c.timeout, check=c.check,
        )
        result = json.loads(out.stdout) if c.json_output and out.rc == 0 else None
        return ExecuteScriptOutput(**out.model_dump(), result=result)
