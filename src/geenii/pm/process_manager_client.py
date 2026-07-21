"""
Synchronous client for the ProcessManager Unix-socket service.

Connects, sends a JSON-RPC request, reads the response, disconnects.
Stateless — each call opens a fresh connection.
"""
from __future__ import annotations

import json
import os
import socket
from typing import Any

from geenii.config import CACHE_DIR

DEFAULT_SOCKET_PATH = os.path.join(CACHE_DIR, "process_manager.sock")


class ProcessManagerClient:

    def __init__(self, socket_path: str = DEFAULT_SOCKET_PATH) -> None:
        self._socket_path = socket_path

    def _call(self, method: str, params: dict | None = None) -> Any:
        #print(f"Connecting to socket at {self._socket_path}")
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(self._socket_path)
            payload = json.dumps({"method": method, "params": params or {}}, separators=(",", ":")) + "\n"
            sock.sendall(payload.encode())

            # read until newline
            buf = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
                if b"\n" in buf:
                    break

            response = json.loads(buf.split(b"\n", 1)[0])
            if not response.get("ok"):
                raise RuntimeError(response.get("error", "Unknown error"))
            return response.get("result")
        finally:
            sock.close()

    def is_available(self) -> bool:
        if not os.path.exists(self._socket_path):
            return False
        try:
            self._call("ping")
            return True
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            return False

    def start(self, command: str, *, env: dict[str, str] | None = None,
              cwd: str | None = None, pid: str | None = None) -> dict:
        return self._call("start", {
            "command": command, "env": env, "cwd": cwd, "pid": pid,
        })

    def status(self, process_id: str) -> dict:
        return self._call("status", {"process_id": process_id})

    def output(self, process_id: str, stream: str = "stdout", tail: int | None = None) -> str:
        return self._call("output", {
            "process_id": process_id, "stream": stream, "tail": tail,
        })

    def kill(self, process_id: str, *, force: bool = False) -> dict:
        return self._call("kill", {"process_id": process_id, "force": force})

    def list(self, *, include_finished: bool = False) -> list[dict]:
        return self._call("list", {"include_finished": include_finished})

    def cleanup(self, process_id: str) -> str:
        return self._call("cleanup", {"process_id": process_id})
