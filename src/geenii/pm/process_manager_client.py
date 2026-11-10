"""
Synchronous client for the process manager, served by the geenii daemon.

Connects, sends a JSON-RPC request, reads the response, disconnects.
Stateless — each call opens a fresh connection.
"""

from __future__ import annotations

from geenii.daemon.client import DEFAULT_SOCKET_PATH, DaemonClient  # noqa: F401  (re-exported)


class ProcessManagerClient(DaemonClient):
    def start(
        self,
        command: str | list[str],
        *,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
        pid: str | None = None,
    ) -> dict:
        """Start a process. A string runs through the shell; a list is executed directly."""
        return self.call(
            "pm.start",
            {
                "command": command,
                "env": env,
                "cwd": cwd,
                "pid": pid,
            },
        )

    def status(self, process_id: str) -> dict:
        return self.call("pm.status", {"process_id": process_id})

    def output(
        self,
        process_id: str,
        stream: str = "stdout",
        tail: int | None = None,
        *,
        offset: int | None = None,
        limit: int | None = None,
    ) -> str:
        """Read the last `tail` lines, or `limit` bytes from byte `offset` (not both)."""
        return self.call(
            "pm.output",
            {
                "process_id": process_id,
                "stream": stream,
                "tail": tail,
                "offset": offset,
                "limit": limit,
            },
        )

    def wait(self, process_id: str, timeout: float | None = None) -> dict:
        """Block until the process has finished; returns its final info."""
        return self.call("pm.wait", {"process_id": process_id, "timeout": timeout})

    def kill(self, process_id: str, *, force: bool = False) -> dict:
        return self.call("pm.kill", {"process_id": process_id, "force": force})

    def list(self, *, include_finished: bool = False) -> list[dict]:
        return self.call("pm.list", {"include_finished": include_finished})

    def cleanup(self, process_id: str) -> str:
        return self.call("pm.cleanup", {"process_id": process_id})

    def gc(
        self,
        max_age: float | None = None,
        *,
        states: list[str] | None = None,
        dry_run: bool = False,
    ) -> list[str]:
        """Remove artifacts of processes finished more than max_age seconds ago; returns their IDs."""
        return self.call(
            "pm.gc", {"max_age": max_age, "states": states, "dry_run": dry_run}
        )
