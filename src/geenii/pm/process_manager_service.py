"""
Unix-socket JSON-RPC service wrapping ProcessManager.

Run standalone:
    python -m geenii.process_manager_service

Protocol: newline-delimited JSON over a Unix domain socket.
    Request:  {"method": "start", "params": {"command": "echo hi"}}\n
    Response: {"ok": true, "result": {...}}\n
    Error:    {"ok": false, "error": "message"}\n
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import sys
from typing import Any

from geenii.config import CACHE_DIR
from geenii.pm.process_manager import ProcessManager

logger = logging.getLogger(__name__)

DEFAULT_SOCKET_PATH = os.path.join(CACHE_DIR, "process_manager.sock")


class ProcessManagerService:

    def __init__(self, socket_path: str = DEFAULT_SOCKET_PATH) -> None:
        self._socket_path = socket_path
        self._pm = ProcessManager()
        self._server: asyncio.AbstractServer | None = None

    @property
    def socket_path(self) -> str:
        return self._socket_path

    async def start(self) -> None:
        os.makedirs(os.path.dirname(self._socket_path), exist_ok=True)
        if os.path.exists(self._socket_path):
            os.unlink(self._socket_path)

        self._server = await asyncio.start_unix_server(
            self._handle_client, path=self._socket_path
        )
        logger.info(f"ProcessManagerService listening on {self._socket_path}")

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        if os.path.exists(self._socket_path):
            os.unlink(self._socket_path)
        logger.info("ProcessManagerService stopped")

    async def serve_forever(self) -> None:
        await self.start()
        stop_event = asyncio.Event()

        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop_event.set)

        logger.info("Service ready, waiting for connections...")
        await stop_event.wait()
        await self.stop()

    # ------------------------------------------------------------------

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        peer = writer.get_extra_info("peername") or "unknown"
        logger.debug(f"Client connected: {peer}")
        try:
            while True:
                line = await reader.readline()
                if not line:
                    break
                try:
                    request = json.loads(line)
                except json.JSONDecodeError as exc:
                    await self._write(writer, {"ok": False, "error": f"Bad JSON: {exc}"})
                    continue

                response = await self._dispatch(request)
                await self._write(writer, response)
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()
            logger.debug(f"Client disconnected: {peer}")

    async def _dispatch(self, request: dict) -> dict[str, Any]:
        method = request.get("method")
        params = request.get("params", {})

        if not method:
            return {"ok": False, "error": "Missing 'method'"}

        handler = {
            "ping": self._rpc_ping,
            "start": self._rpc_start,
            "status": self._rpc_status,
            "output": self._rpc_output,
            "kill": self._rpc_kill,
            "list": self._rpc_list,
            "cleanup": self._rpc_cleanup,
        }.get(method)

        if handler is None:
            return {"ok": False, "error": f"Unknown method: {method}"}

        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(None, lambda: handler(params))
            return {"ok": True, "result": result}
        except Exception as exc:
            logger.exception(f"Error in {method}")
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    @staticmethod
    async def _write(writer: asyncio.StreamWriter, data: dict) -> None:
        writer.write(json.dumps(data, separators=(",", ":")).encode() + b"\n")
        await writer.drain()

    # ------------------------------------------------------------------
    # RPC handlers — all run in the thread-pool executor
    # ------------------------------------------------------------------

    def _rpc_ping(self, params: dict) -> str:
        return "pong"

    def _rpc_start(self, params: dict) -> dict:
        info = self._pm.start(
            params["command"],
            env=params.get("env"),
            cwd=params.get("cwd") or None,
            pid=params.get("pid") or None,
        )
        return info.to_dict()

    def _rpc_status(self, params: dict) -> dict:
        info = self._pm.status(params["process_id"])
        return info.to_dict()

    def _rpc_output(self, params: dict) -> str:
        tail = params.get("tail")
        return self._pm.output(
            params["process_id"],
            stream=params.get("stream", "stdout"),
            tail=tail if tail and tail > 0 else None,
        )

    def _rpc_kill(self, params: dict) -> dict:
        info = self._pm.kill(params["process_id"], force=params.get("force", False))
        return info.to_dict()

    def _rpc_list(self, params: dict) -> list[dict]:
        procs = self._pm.list(include_finished=params.get("include_finished", False))
        return [p.to_dict() for p in procs]

    def _rpc_cleanup(self, params: dict) -> str:
        self._pm.cleanup(params["process_id"])
        return "ok"


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    socket_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SOCKET_PATH
    service = ProcessManagerService(socket_path)
    asyncio.run(service.serve_forever())


if __name__ == "__main__":
    main()
