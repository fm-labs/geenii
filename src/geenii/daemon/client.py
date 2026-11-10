"""
Synchronous client for the geenii daemon socket.

Connects, sends a JSON-RPC request, reads the response, disconnects.
Stateless — each call opens a fresh connection.
"""

from __future__ import annotations

import json
import os
import socket
from typing import Any

from geenii.config import GEENII_CACHE_DIR

DEFAULT_SOCKET_PATH = os.path.join(GEENII_CACHE_DIR, "geenii.sock")

# Checked in order when no socket path is passed explicitly
SOCKET_ENV_VARS = ("GEENII_SOCKET", "GEENII_PM_SOCKET")


def default_socket_path() -> str:
    for name in SOCKET_ENV_VARS:
        if os.environ.get(name):
            return os.environ[name]
    return DEFAULT_SOCKET_PATH


class DaemonClient:
    def __init__(self, socket_path: str | None = None) -> None:
        self._socket_path = socket_path or default_socket_path()

    @property
    def socket_path(self) -> str:
        return self._socket_path

    def call(self, method: str, params: dict | None = None) -> Any:
        """Call a daemon method. Raises RuntimeError with the daemon's message on errors."""
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(self._socket_path)
            payload = (
                json.dumps(
                    {"method": method, "params": params or {}}, separators=(",", ":")
                )
                + "\n"
            )
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
            self.call("ping")
            return True
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            return False

    def info(self) -> dict:
        return self.call("daemon.info")

    def shutdown(self) -> str:
        return self.call("daemon.shutdown")
