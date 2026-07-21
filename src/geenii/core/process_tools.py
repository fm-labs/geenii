"""Tools for managing background processes via the ProcessManager service."""
import json
import logging

from geenii.pm.process_manager_client import ProcessManagerClient
from geenii.tool.registry import ToolRegistry

logger = logging.getLogger(__name__)


def init_process_tools(tool_registry: ToolRegistry, client: ProcessManagerClient) -> None:

    @tool_registry.tool(name="bg_process_start")
    def start_process(command: str, working_directory: str = "", process_id: str = "") -> str:
        """
        Start a long-running command as a background process.
        Returns immediately with a process ID that can be used to check status and retrieve output later.

        :param command: The shell command to run, e.g. "python3 train.py --epochs 10".
        :param working_directory: Working directory for the process. Uses current directory if empty.
        :param process_id: Optional custom process ID. Auto-generated if empty.
        :return: JSON with the assigned process ID and initial state.
        """
        result = client.start(
            command,
            cwd=working_directory or None,
            pid=process_id or None,
        )
        return json.dumps(result, indent=2)

    @tool_registry.tool(name="bg_process_status")
    def process_status(process_id: str) -> str:
        """
        Check the current state of a background process.

        :param process_id: The process ID returned by bg_process_start.
        :return: JSON with state (running/completed/failed/killed), exit code, and timing info.
        """
        try:
            result = client.status(process_id)
            return json.dumps(result, indent=2)
        except RuntimeError as exc:
            return json.dumps({"error": str(exc)})

    @tool_registry.tool(name="bg_process_output")
    def process_output(process_id: str, stream: str = "stdout", tail: int = 0) -> str:
        """
        Retrieve captured output from a background process. Can be called while the process is still running to see partial output.

        :param process_id: The process ID returned by bg_process_start.
        :param stream: Which output stream to read: "stdout" or "stderr".
        :param tail: If greater than 0, return only the last N lines. 0 returns all output.
        :return: The captured output text.
        """
        try:
            return client.output(
                process_id,
                stream=stream,
                tail=tail if tail > 0 else None,
            )
        except RuntimeError as exc:
            return f"Error: {exc}"

    @tool_registry.tool(name="bg_process_kill")
    def kill_process(process_id: str, force: bool = False) -> str:
        """
        Kill a running background process.

        :param process_id: The process ID returned by bg_process_start.
        :param force: If true, send SIGKILL instead of SIGTERM.
        :return: JSON with the updated process state.
        """
        try:
            result = client.kill(process_id, force=force)
            return json.dumps(result, indent=2)
        except RuntimeError as exc:
            return json.dumps({"error": str(exc)})

    @tool_registry.tool(name="bg_process_list")
    def list_processes(include_finished: bool = False) -> str:
        """
        List background processes.

        :param include_finished: If true, also include completed/failed/killed processes from disk.
        :return: JSON array of process info objects.
        """
        result = client.list(include_finished=include_finished)
        return json.dumps(result, indent=2)
