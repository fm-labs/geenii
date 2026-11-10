from __future__ import annotations

import inspect
import json
import logging
import os
import shlex
import subprocess
from collections.abc import Callable
from typing import Any

from geenii.tool.common import (
    Tool,
    ToolCallContext,
    ToolCallResult,
    expand_vars,
    to_tool_call_result,
)
from geenii.utils.async_bridge import run_sync

logger = logging.getLogger(__name__)


class PythonFunctionTool(Tool):
    """A tool backed by a plain Python callable."""

    def __init__(
        self,
        name: str,
        description: str = "",
        input_schema: dict | None = None,
        handler: Callable[..., Any] | None = None,
    ):
        super().__init__(name, description, input_schema)
        self.type = "function"
        self.handler = handler

    def invoke(
        self,
        args: dict[str, Any],
        env: dict[str, str] | None = None,
        *,
        ctx: ToolCallContext,
    ) -> ToolCallResult:
        if self.handler is None:
            raise RuntimeError(f"No handler registered for tool {self.name!r}")

        try:
            # support sync and async handlers
            result = self.handler(**args)
            if inspect.isawaitable(result):
                result = run_sync(result)
        except Exception as e:
            logger.error(
                f"Error during python fn tool {self.name!r}: {e}", exc_info=True
            )
            result = e

        # print(f"Tool {self.name!r} returned:", result)
        return to_tool_call_result(result)


class PythonCliTool(Tool):
    """A ComputerTool that executes Python scripts on Unix-like systems."""

    def __init__(
        self,
        name: str,
        description: str = "",
        input_schema: dict | None = None,
    ):
        super().__init__(name, description, input_schema)
        self.type = "python"

    def invoke(
        self,
        args: dict[str, Any],
        env: dict[str, str] | None = None,
        *,
        ctx: ToolCallContext,
    ) -> ToolCallResult:
        command = args.get("command")
        if not command:
            raise ValueError(f"Missing 'command' argument for PythonTool {self.name!r}")

        # expand environment variables in the command
        command = expand_vars(command, env or {})
        _command = shlex.split(command)

        _env = os.environ.copy()
        if env:
            _env.update(env)

        working_dir = ctx.cwd
        # the unexpanded command, since env may hold secrets
        logger.info(
            f"Spawn python subprocess with command={args.get('command')!r} in directory: {working_dir!r}"
        )
        p = subprocess.run(
            _command,
            shell=False,
            capture_output=True,
            text=True,
            env=_env,
            cwd=working_dir,
        )
        logger.info(f"PythonCliTool output: {p.stdout}")
        logger.info(f"PythonCliTool error: {p.stderr}")
        logger.info(f"PythonCliTool rc: {p.returncode}")

        out = p.stdout.strip()
        # attempt json parsing
        json_data = None
        if p.returncode == 0 and len(out) > 0:
            try:
                json_data = json.loads(out)
            except json.decoder.JSONDecodeError:
                pass

        err = p.stderr.strip()
        _output = f"stdout:\n{out}\nstderr:\n{err}"
        if p.returncode != 0:
            _output += f"\nEXITED WITH NON-ZERO EXIT CODE: {p.returncode}"
            return ToolCallResult(text=_output, is_error=True)
        return ToolCallResult(
            text=_output, is_error=False, structured_content=json_data
        )
