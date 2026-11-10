from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

from geenii.tool.common import Tool, ToolCallResult

logger = logging.getLogger(__name__)


class ScriptTool(Tool):
    """A tool backed by an executable script file in a skill's scripts/ directory."""

    def __init__(
        self,
        name: str,
        description: str,
        script_path: str,
        input_schema: dict | None = None,
    ):
        super().__init__(name, description, input_schema)
        self.type = "function"
        self.script_path = script_path

    def invoke(
        self, args: dict[str, Any], env: dict[str, str] | None = None, **kwargs: Any
    ) -> ToolCallResult:
        arg_str = args.get("args")
        cmd = [self.script_path]
        if arg_str:
            cmd.extend(shlex.split(arg_str))
        # print("ScriptTool CMD", cmd)

        _env = os.environ.copy()
        if env:
            _env.update(env)

        result = subprocess.run(
            cmd,
            # input=input_json,
            capture_output=True,
            text=True,
            env=_env,
            cwd=str(Path(self.script_path).parent),
        )

        logger.info("ScriptTool %s exited with code %d", self.name, result.returncode)
        output = result.stdout.strip()
        err = result.stderr.strip()
        text = f"{output}\n{err}"

        # attempt json parsing
        json_data = None
        try:
            json_data = json.loads(text)
        except json.decoder.JSONDecodeError:
            pass
        return ToolCallResult(
            text=text,
            structured_content=json_data,
            is_error=result.returncode != 0,
        )
