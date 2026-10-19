from __future__ import annotations

import json
import logging
import subprocess
import os
import uuid
from typing import Any

from geenii import config
from geenii.tool.common import Tool, expand_vars, ToolCallResult

logger = logging.getLogger(__name__)

class ComputerTool(Tool):
    """A tool that executes a command on the local machine."""

    def __init__(
        self,
        name: str,
        description: str = "",
        input_schema: dict | None = None,
        command_template: str | None = None,
    ):
        super().__init__(name, description, input_schema)
        self.type = "computer"
        self.command_template = command_template

    def invoke(self, args: dict[str,Any], env: dict[str, str] | None = None, **kwargs: Any) -> ToolCallResult:
        working_dir = kwargs.get("cwd") or config.GEENII_WORKING_DIR
        # todo check if tool execution is permitted in given working_dir

        command = args.get("command")
        if not command:
            raise ValueError(f"Missing 'command' argument for ComputerTool {self.name!r}")
        if self.command_template is not None:
            # `command` is in args too, so it must not be passed twice
            command = self.command_template.format(**{**args, "command": command})

        logger.info(f"Executing ComputerTool command: {command} in working directory={working_dir}")
        subprocess_id = uuid.uuid4().hex[:8]
        # logged before expansion and with env names only, since env may hold secrets
        logger.info(f"Subprocess [{subprocess_id}] Spawning command={command!r} environment={sorted(env or {})} cwd={working_dir}")
        command = expand_vars(command, env or {})

        _env = os.environ.copy()
        if env:
            _env.update(env)
        p = subprocess.run(command, shell=True, capture_output=True, text=True, env=_env, cwd=working_dir)
        logger.info(f"Subprocess [{subprocess_id}] Return code: {p.returncode}")
        logger.info(f"Subprocess [{subprocess_id}] Standard output: {p.stdout}")
        logger.info(f"Subprocess [{subprocess_id}] Standard error: {p.stderr}")

        out = p.stdout.strip()
        # attempt json parsing; only an object is structured content
        json_data = None
        try:
            json_data = json.loads(out)
        except json.decoder.JSONDecodeError:
            pass
        if not isinstance(json_data, dict): # and not isinstance(json_data, list):
            json_data = None

        err = p.stderr.strip()
        _output = f"stdout:\n{out}\nstderr:\n{err}"
        if p.returncode != 0:
            _output += f"\nEXITED WITH NON-ZERO EXIT CODE: { p.returncode}"
            return ToolCallResult(text=_output, is_error=True)
        return ToolCallResult(text=_output, is_error=False, structured_content=json_data)


class AppleScriptTool(ComputerTool):

    """A ComputerTool that executes AppleScript commands on MacOS."""

    def __init__(
        self,
        name: str,
        description: str = "",
        input_schema: dict | None = None,
    ):
        super().__init__(name, description, input_schema, command_template="osascript -e '{command}'")
