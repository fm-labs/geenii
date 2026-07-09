from __future__ import annotations

import logging
import subprocess
import os
import shlex
import uuid
import asyncio
from typing import Any

from geenii.tool.common import Tool, expand_vars

logger = logging.getLogger(__name__)

class ComputerTool(Tool):
    """A tool that executes a command on the local machine."""

    def __init__(
        self,
        name: str,
        description: str = "",
        parameters: dict | None = None,
        command_template: str | None = None,
    ):
        super().__init__(name, description, parameters)
        self.type = "computer"
        self.command_template = command_template

    async def invoke(self, args: dict[str,Any], env: dict[str, str] | None = None, **kwargs: Any) -> Any:
        command = args.get("command")
        if not command:
            raise ValueError(f"Missing 'command' argument for ComputerTool {self.name!r}")

        if self.command_template is not None:
            command = self.command_template.format(command=command, **args)

        logger.info(f"Executing ComputerTool command: {command}")

        # expand environment variables in the command
        command = expand_vars(command, env or {})

        # run the command in a thread to avoid blocking the event loop
        result = await asyncio.to_thread(self.run_subprocess, command, env)
        logger.info(f"Command result: {result}")
        return result


    def run_subprocess(self, command: str, env: dict[str, str] | None) -> str:
        subprocess_id = uuid.uuid4().hex[:8]
        logger.info(f"[{subprocess_id}] Spawn subprocess with command={command} environment={env}")
        _command = shlex.split(command)
        print(_command)

        _env = os.environ.copy()
        if env:
            _env.update(env)
        _result = subprocess.run(_command, shell=False, capture_output=True, text=True, env=_env, cwd=None)
        logger.info(f"[{subprocess_id}] Return code: {_result.returncode}")
        logger.info(f"[{subprocess_id}] Standard output: {_result.stdout}")
        logger.info(f"[{subprocess_id}] Standard error: {_result.stderr}")
        _output = _result.stdout.strip()
        if _result.returncode != 0:
            _output += f"EXITED WITH NON-ZERO EXIT CODE: { _result.returncode}" + _result.stderr.strip()
        return _output


class AppleScriptTool(ComputerTool):

    """A ComputerTool that executes AppleScript commands on MacOS."""

    def __init__(
        self,
        name: str,
        description: str = "",
        parameters: dict | None = None,
    ):
        super().__init__(name, description, parameters, command_template="osascript -e '{command}'")
