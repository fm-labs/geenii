from __future__ import annotations

import json
import logging
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

from geenii import config
from geenii.tool.common import (
    Tool,
    ToolCallContext,
    ToolCallResult,
    expand_vars,
    to_tool_call_result,
)

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

    def invoke(
        self,
        args: dict[str, Any],
        env: dict[str, str] | None = None,
        *,
        ctx: ToolCallContext,
    ) -> ToolCallResult:
        working_dir = ctx.cwd
        # todo check if tool execution is permitted in given working_dir

        command = args.get("command")
        if not command:
            raise ValueError(
                f"Missing 'command' argument for ComputerTool {self.name!r}"
            )
        if self.command_template is not None:
            # `command` is in args too, so it must not be passed twice
            command = self.command_template.format(**{**args, "command": command})

        logger.info(
            f"Executing ComputerTool command: {command} in working directory={working_dir}"
        )
        subprocess_id = uuid.uuid4().hex[:8]
        # logged before expansion and with env names only, since env may hold secrets
        logger.info(
            f"ComputerTool [{subprocess_id}] Spawning command={command!r} environment={sorted(env or {})} cwd={working_dir}"
        )
        command = expand_vars(command, env or {})

        _env = os.environ.copy()
        if env:
            _env.update(env)
        p = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            env=_env,
            cwd=working_dir,
        )
        logger.info(f"ComputerTool [{subprocess_id}] Standard output: {p.stdout}")
        logger.info(f"ComputerTool [{subprocess_id}] Standard error: {p.stderr}")
        logger.info(f"ComputerTool [{subprocess_id}] Return code: {p.returncode}")

        out = p.stdout.strip()
        # attempt json parsing; only an object is structured content
        json_data = None
        try:
            json_data = json.loads(out)
        except json.decoder.JSONDecodeError:
            pass
        if not isinstance(json_data, dict):  # and not isinstance(json_data, list):
            json_data = None

        err = p.stderr.strip()
        _output = f"stdout:\n{out}\nstderr:\n{err}"
        if p.returncode != 0:
            _output += f"\nEXITED WITH NON-ZERO EXIT CODE: {p.returncode}"
            return ToolCallResult(text=_output, is_error=True)
        return ToolCallResult(
            text=_output, is_error=False, structured_content=json_data
        )


class AppleScriptTool(ComputerTool):
    """A ComputerTool that executes AppleScript commands on MacOS."""

    def __init__(
        self,
        name: str,
        description: str = "",
        input_schema: dict | None = None,
    ):
        super().__init__(
            name, description, input_schema, command_template="osascript -e '{command}'"
        )


class ReadTool(Tool):
    """A Tool that reads data from a source."""

    NAME = "read"
    DESCRIPTION = "Read data from a source"
    INPUT_SCHEMA = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
        },
        "required": ["file_path"],
    }

    def __init__(self):
        super().__init__(self.NAME, self.DESCRIPTION, self.INPUT_SCHEMA)

    def invoke(
        self,
        args: dict[str, Any],
        env: dict[str, str] | None = None,
        *,
        ctx: ToolCallContext,
    ) -> ToolCallResult:
        file_path = args.get("file_path")
        try:
            if not file_path or not isinstance(file_path, str):
                raise ValueError(
                    f"Invalid file_path argument for ReadTool {self.name!r}"
                )

            wd = ctx.cwd
            file_path = _normalize_path(file_path, wd)
            if not is_file_in_allowed_dirs(file_path, wd):
                logger.critical(
                    f"SECURITY ALERT! Attempting to read file from {file_path}. wd={wd}"
                )
                raise ValueError(f"You are not allowed to read this file: {file_path}")

            logger.warning(f"file_read: {file_path}")
            with open(file_path, "r") as f:
                return to_tool_call_result(f.read())
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            return to_tool_call_result(e)


class WriteTool(Tool):
    """A Tool that writes data to a source."""

    NAME = "write"
    DESCRIPTION = "Write data to a source"
    INPUT_SCHEMA = {
        "type": "object",
        "properties": {
            "file_path": {"type": "string"},
            "contents": {"type": "string"},
        },
        "required": ["file_path", "contents"],
    }

    def __init__(self):
        super().__init__(self.NAME, self.DESCRIPTION, self.INPUT_SCHEMA)

    def invoke(
        self,
        args: dict[str, Any],
        env: dict[str, str] | None = None,
        *,
        ctx: ToolCallContext,
    ) -> ToolCallResult:
        file_path = args.get("file_path")
        contents = args.get("contents", "")
        try:
            if not file_path or not isinstance(file_path, str):
                raise ValueError(
                    f"Invalid file_path argument for WriteTool {self.name!r}"
                )

            wd = ctx.cwd
            file_path = _normalize_path(file_path, wd)

            if not is_file_in_allowed_dirs(file_path, wd):
                logger.critical(
                    f"SECURITY ALERT! Attempting to write to {file_path}. wd={wd}"
                )
                raise ValueError(f"You are not allowed to write this file: {file_path}")

            logger.warning(f"file_write: {file_path}")
            with open(file_path, "w") as f:
                f.write(contents)

            return ToolCallResult(f"Contents successfully written to {file_path}")
        except Exception as e:
            logger.error(f"Error writing file {file_path}: {e}")
            return to_tool_call_result(e)


def _normalize_path(path: str, base_dir: str) -> str:
    if not Path(path).is_absolute():
        path = Path(base_dir) / path
        return str(path.resolve(strict=False).absolute())
    return str(Path(path).resolve(strict=False).absolute())


def is_file_in_allowed_dirs(file_path: str | Path, wd: str | None = None) -> bool:
    dirs = [wd, config.GEENII_WORKING_DIR]
    user_settings = config.read_user_settings()
    if "allowed_dirs" in user_settings and isinstance(
        user_settings["allowed_dirs"], list
    ):
        allowed_dirs = user_settings["allowed_dirs"]
        dirs.extend(allowed_dirs)

    for _dir in dirs:
        if _dir is not None and is_file_in_allowed_dir(file_path, wd=_dir):
            return True
    return False


def is_file_in_allowed_dir(file_path: str | Path, wd: str) -> bool:
    """Return True if file_path resolves to a location inside the working dir."""
    try:
        logger.debug(f"check is_file_in_working_dir file_path={file_path} wd={wd}")
        wd = Path(wd).resolve(strict=False)
        target = Path(file_path).resolve(strict=False)
    except (OSError, ValueError):
        # null bytes, embedded NULs, unresolvable paths, symlink loops
        return False
    return target != wd and wd in target.parents
