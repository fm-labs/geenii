from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

from geenii.tool.common import Tool

logger = logging.getLogger(__name__)


class ScriptTool(Tool):
    """A tool backed by an executable script file in a skill's scripts/ directory."""

    def __init__(self, name: str, description: str, script_path: str, parameters: dict | None = None):
        super().__init__(name, description, parameters)
        self.type = "function"
        self.script_path = script_path

    async def invoke(self, args: dict[str, Any], env: dict[str, str] | None = None, **kwargs: Any) -> Any:
        input_json = json.dumps(args)
        _env = os.environ.copy()
        if env:
            _env.update(env)

        result = await asyncio.to_thread(
            subprocess.run,
            [self.script_path],
            input=input_json,
            capture_output=True,
            text=True,
            env=_env,
            cwd=str(Path(self.script_path).parent),
        )

        logger.info("ScriptTool %s exited with code %d", self.name, result.returncode)
        output = result.stdout.strip()
        if result.returncode != 0:
            return {"error": result.stderr.strip(), "output": output}
        return {"output": output}
