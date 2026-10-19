from __future__ import annotations

import json
import logging
import subprocess
import shlex
import os
import inspect
from typing import Callable, Any

from geenii.tool.common import Tool, expand_vars, ToolCallResult
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

    def invoke(self, args: dict[str, Any], env: dict[str, str] | None = None, **kwargs: Any) -> ToolCallResult:
        if self.handler is None:
            raise RuntimeError(f"No handler registered for tool {self.name!r}")

        # support sync and async handlers
        result = self.handler(**args)
        if inspect.isawaitable(result):
            result = run_sync(result)

        # print(f"Tool {self.name!r} returned:", result)
        return _to_tool_call_result(result)


def _to_tool_call_result(result: Any) -> ToolCallResult:
    """Map a handler's return value to a ToolCallResult. `text` is always a string; dicts are also structured content."""
    if isinstance(result, ToolCallResult):
        return result
    if result is None:
        return ToolCallResult(text="")
    if isinstance(result, str):
        return ToolCallResult(text=result)
    if isinstance(result, bytes):
        return ToolCallResult(text=result.decode("utf-8", errors="replace"))
    if isinstance(result, dict):
        return ToolCallResult(text=json.dumps(result, default=str), structured_content=result)
    if isinstance(result, (list, tuple)):
        return ToolCallResult(text=json.dumps(result, default=str))
    return ToolCallResult(text=str(result))


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

    def invoke(self, args: dict[str, Any], env: dict[str, str] | None = None, **kwargs: Any) -> ToolCallResult:
        command = args.get("command")
        if not command:
            raise ValueError(f"Missing 'command' argument for PythonTool {self.name!r}")

        # expand environment variables in the command
        command = expand_vars(command, env or {})
        _command = shlex.split(command)

        _env = os.environ.copy()
        if env:
            _env.update(env)

        # the unexpanded command, since env may hold secrets
        logger.info(f"Spawn python subprocess with command={args.get('command')!r}")
        p = subprocess.run(_command, shell=False, capture_output=True, text=True, env=_env, cwd=None)
        logger.info(f"Return code: {p.returncode}")
        logger.info(f"Standard output: {p.stdout}")
        logger.info(f"Standard error: {p.stderr}")

        out = p.stdout.strip()
        # attempt json parsing
        json_data = None
        try:
            json_data = json.loads(out)
        except json.decoder.JSONDecodeError:
            pass

        err = p.stderr.strip()
        _output = f"stdout:\n{out}\nstderr:\n{err}"
        if p.returncode != 0:
            _output += f"\nEXITED WITH NON-ZERO EXIT CODE: { p.returncode}"
            return ToolCallResult(text=_output, is_error=True)
        return ToolCallResult(text=_output, is_error=False, structured_content=json_data)
