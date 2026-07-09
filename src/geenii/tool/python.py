from __future__ import annotations

import logging
import subprocess
import shlex
import asyncio
import os
import inspect
from typing import Callable, Any

from geenii.tool.common import Tool, expand_vars

logger = logging.getLogger(__name__)


class PythonFunctionTool(Tool):
    """A tool backed by a plain Python callable."""

    def __init__(
            self,
            name: str,
            description: str = "",
            parameters: dict | None = None,
            handler: Callable[..., Any] | None = None,
    ):
        super().__init__(name, description, parameters)
        self.type = "function"
        self.handler = handler

    async def invoke(self, args: dict[str, Any], env: dict[str, str] | None = None, **kwargs: Any) -> Any:
        if self.handler is None:
            raise RuntimeError(f"No handler registered for tool {self.name!r}")

        # support sync and async handlers
        if inspect.iscoroutinefunction(self.handler):
            result = await self.handler(**args)
        else:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: self.handler(**args))

        # print(f"Tool {self.name!r} returned:", result)
        return result


class PythonCliTool(Tool):
    """A ComputerTool that executes Python scripts on Unix-like systems."""

    def __init__(
            self,
            name: str,
            description: str = "",
            parameters: dict | None = None,
    ):
        super().__init__(name, description, parameters)
        self.type = "python"

    async def invoke(self, args: dict[str, Any], env: dict[str, str] | None = None, **kwargs: Any) -> Any:
        command = args.get("command")
        if not command:
            raise ValueError(f"Missing 'command' argument for PythonTool {self.name!r}")

        logger.info(f"Invoking PythonTool raw command: {command}")

        # expand environment variables in the command
        command = expand_vars(command, env or {})

        # run the command in a thread to avoid blocking the event loop
        result: str = await asyncio.to_thread(self.run_subprocess, command, env)
        logger.info(f"PythonCliTool result: {str(result)}")
        return result

    # helper method to run a subprocess and capture its output
    def run_subprocess(self, command: str, env: dict[str, str] | None) -> str:
        logger.info(f"Spawn subprocess with command={command} environment={env}")
        _command = shlex.split(command)
        print(_command)

        _env = os.environ.copy()
        if env:
            _env.update(env)
        _result = subprocess.run(_command, shell=False, capture_output=True, text=True, env=_env, cwd=None)
        logger.info(f"Return code: {_result.returncode}")
        logger.info(f"Standard output: {_result.stdout}")
        logger.info(f"Standard error: {_result.stderr}")
        _output = _result.stdout.strip()
        if _result.returncode != 0:
            _output += "ERROR: " + _result.stderr.strip()
        print("OUTPUT:", _output)
        return _output
