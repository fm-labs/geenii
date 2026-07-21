from __future__ import annotations

import asyncio
import logging
import shlex
import shutil
from typing import Any, Literal

from geenii.tool.common import Tool, expand_vars

logger = logging.getLogger(__name__)

SANDBOX_CLASSES = {
    "python": "PythonSandbox",
    "bash": "BashSandbox",
    "node": "NodeJsSandbox",
}


def _docker_available() -> bool:
    return shutil.which("docker") is not None


class SandboxTool(Tool):
    """A tool that executes a command inside a Docker sandbox container."""

    def __init__(
        self,
        name: str,
        description: str = "",
        parameters: dict | None = None,
        runtime: Literal["python", "node", "bash"] = "bash",
        network_mode: Literal["none", "bridge", "host"] = "none",
        cpu_limit: float = 0.5,
        mem_limit: str = "256m",
        pid_limit: int = 100,
        timeout: int = 30,
    ):
        super().__init__(name, description, parameters)
        self.type = "sandbox"
        self.runtime = runtime
        self.network_mode = network_mode
        self.cpu_limit = cpu_limit
        self.mem_limit = mem_limit
        self.pid_limit = pid_limit
        self.timeout = timeout

    async def invoke(self, args: dict[str, Any], env: dict[str, str] | None = None, **kwargs: Any) -> Any:
        command = args.get("command", "")
        if not command:
            raise ValueError(f"Missing 'command' argument for SandboxTool {self.name!r}")

        if not _docker_available():
            raise RuntimeError("Docker is not installed or not on PATH")

        command = expand_vars(command, env or {})

        app_dir = (env or {}).get("SKILL_DIR") or (env or {}).get("SCRIPT_DIR")
        if not app_dir:
            raise ValueError(
                "SandboxTool requires SKILL_DIR or SCRIPT_DIR in the tool environment. "
                "Attach this tool to an agent that has a skill selected."
            )

        sandbox_id = (env or {}).get("SKILL_NAME", "sandbox")

        result = await asyncio.to_thread(
            self._run, app_dir=app_dir, command=command, sandbox_id=sandbox_id, env=env,
        )
        return result

    def _run(self, app_dir: str, command: str, sandbox_id: str, env: dict[str, str] | None) -> str:
        from geenii.sandbox import PythonSandbox, BashSandbox, NodeJsSandbox

        shared_kwargs = dict(
            app_dir=app_dir,
            network_mode=self.network_mode,
            cpu_limit=self.cpu_limit,
            mem_limit=self.mem_limit,
            pid_limit=self.pid_limit,
            timeout=self.timeout,
            env=env,
            sandbox_id=sandbox_id,
        )

        if self.runtime == "bash":
            sandbox = BashSandbox(shell_command=command, **shared_kwargs)
        elif self.runtime == "python":
            parts = shlex.split(command)
            sandbox = PythonSandbox(
                script_name=parts[0] if parts else "main.py",
                script_args=parts[1:] or None,
                **shared_kwargs,
            )
        elif self.runtime == "node":
            parts = shlex.split(command)
            sandbox = NodeJsSandbox(
                script_name=parts[0] if parts else "index.js",
                script_args=parts[1:] or None,
                **shared_kwargs,
            )
        else:
            raise ValueError(f"Unknown sandbox runtime: {self.runtime!r}")

        logger.info("SandboxTool building %s sandbox app_dir=%s", self.runtime, app_dir)
        sandbox.build()

        logger.info("SandboxTool running: %s", command)
        rc, stdout, stderr = sandbox.run()
        logger.info("SandboxTool exit_code=%d", rc)

        if rc == 0:
            return stdout.strip()
        return f"EXIT CODE {rc}\n{stdout}\n{stderr}".strip()
