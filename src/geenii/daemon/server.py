"""
Unix-socket JSON-RPC server for the geenii daemon.

Run standalone:
    geenii daemon start [--socket PATH] [--scheduler-config PATH]
    python -m geenii.daemon.server [--socket PATH] [--scheduler-config PATH]

Protocol: newline-delimited JSON over a Unix domain socket.
    Request:  {"method": "pm.start", "params": {"command": "echo hi"}}\n
    Response: {"ok": true, "result": {...}}\n
    Error:    {"ok": false, "error": "message"}\n

Methods: ping, daemon.info, daemon.shutdown, plus everything ProcessHost
registers (pm.*, scheduler.*, supervisor.*, and the unprefixed pm aliases).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import time
from typing import Any, Optional

from geenii import proc as proc_util
from geenii.config import GEENII_WORKING_DIR
from geenii.daemon.client import default_socket_path
from geenii.daemon.host import ProcessHost
from geenii.scheduler import Scheduler

logger = logging.getLogger(__name__)

DEFAULT_SCHEDULER_CONFIG = os.path.join(GEENII_WORKING_DIR, ".geenii", "scheduler.json")
DEFAULT_SERVICES_CONFIG = os.path.join(GEENII_WORKING_DIR, ".geenii", "services.json")


class DaemonAlreadyRunning(RuntimeError):
    pass


class DaemonServer:

    def __init__(self, host: ProcessHost, socket_path: Optional[str] = None) -> None:
        self._host = host
        self._socket_path = socket_path or default_socket_path()
        self._server: asyncio.AbstractServer | None = None
        self._stop_event = asyncio.Event()
        self._started_at: float | None = None
        self._stopped = False

    @property
    def socket_path(self) -> str:
        return self._socket_path

    @property
    def host(self) -> ProcessHost:
        return self._host

    async def start(self) -> None:
        os.makedirs(os.path.dirname(self._socket_path), exist_ok=True)
        if os.path.exists(self._socket_path):
            if await self._socket_is_live():
                raise DaemonAlreadyRunning(f"A geenii daemon is already running on {self._socket_path}")
            os.unlink(self._socket_path)  # stale socket from a crashed daemon

        # Components first (recovers process records), then accept connections
        await self._host.start()
        try:
            self._server = await asyncio.start_unix_server(self._handle_client, path=self._socket_path)
        except BaseException:
            await self._host.stop()
            raise
        self._started_at = time.time()
        logger.info(f"geenii daemon listening on {self._socket_path}")

    async def stop(self) -> None:
        if self._stopped:
            return
        self._stopped = True
        if self._server:
            self._server.close()
        await self._host.stop()
        if self._server:
            await self._server.wait_closed()
        if os.path.exists(self._socket_path):
            os.unlink(self._socket_path)
        logger.info("geenii daemon stopped")

    async def serve_forever(self) -> None:
        await self.start()
        proc_util.add_shutdown_handlers(self._stop_event.set)
        logger.info("Daemon ready, waiting for connections...")
        await self._stop_event.wait()
        await self.stop()

    def request_shutdown(self) -> None:
        self._stop_event.set()

    # ------------------------------------------------------------------

    async def _socket_is_live(self) -> bool:
        try:
            _, writer = await asyncio.open_unix_connection(self._socket_path)
        except (ConnectionRefusedError, FileNotFoundError, OSError):
            return False
        writer.close()
        await writer.wait_closed()
        return True

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
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
                if not isinstance(request, dict):
                    await self._write(writer, {"ok": False, "error": "Request must be a JSON object"})
                    continue
                await self._write(writer, await self._dispatch(request))
        except (ConnectionResetError, BrokenPipeError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionResetError, BrokenPipeError):
                pass

    async def _dispatch(self, request: dict) -> dict[str, Any]:
        method = request.get("method")
        params = request.get("params") or {}

        if not method:
            return {"ok": False, "error": "Missing 'method'"}

        handler = {
            "ping": self._rpc_ping,
            "daemon.info": self._rpc_info,
            "daemon.shutdown": self._rpc_shutdown,
        }.get(method) or self._host.methods.get(method)

        if handler is None:
            return {"ok": False, "error": f"Unknown method: {method}"}

        try:
            return {"ok": True, "result": await handler(params)}
        except Exception as exc:
            logger.exception(f"Error in {method}")
            return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    @staticmethod
    async def _write(writer: asyncio.StreamWriter, data: dict) -> None:
        writer.write(json.dumps(data, separators=(",", ":")).encode() + b"\n")
        await writer.drain()

    async def _rpc_ping(self, params: dict) -> str:
        return "pong"

    async def _rpc_info(self, params: dict) -> dict:
        return {
            "pid": os.getpid(),
            "socket": self._socket_path,
            "uptime_s": round(time.time() - self._started_at, 3) if self._started_at else 0.0,
            **await self._host.info(),
        }

    async def _rpc_shutdown(self, params: dict) -> str:
        # Reply first; serve_forever() performs the actual stop
        asyncio.get_running_loop().call_soon(self.request_shutdown)
        return "shutting down"


def build_host(
    scheduler_config: Optional[str] = DEFAULT_SCHEDULER_CONFIG,
    services_config: Optional[str] = DEFAULT_SERVICES_CONFIG,
) -> ProcessHost:
    """Create a ProcessHost for the given config files (each is optional and may not exist yet)."""
    scheduler = Scheduler()
    if scheduler_config and os.path.isfile(scheduler_config):
        scheduler.load_config(scheduler_config)
    elif scheduler_config:
        logger.info("No scheduler config at %s; the scheduler starts without tasks", scheduler_config)
    if services_config and not os.path.isfile(services_config):
        logger.info("No services config at %s; no services are started", services_config)
    return ProcessHost(scheduler=scheduler, scheduler_config=scheduler_config, services_config=services_config)


def run_daemon(
    socket_path: Optional[str] = None,
    scheduler_config: Optional[str] = DEFAULT_SCHEDULER_CONFIG,
    services_config: Optional[str] = DEFAULT_SERVICES_CONFIG,
) -> None:
    """Run the daemon in the foreground until SIGINT/SIGTERM or daemon.shutdown."""
    server = DaemonServer(build_host(scheduler_config, services_config), socket_path)
    asyncio.run(server.serve_forever())


def main(argv: Optional[list[str]] = None) -> None:
    from geenii.logs import init_logging
    init_logging()

    parser = argparse.ArgumentParser(prog="geenii-daemon", description="Run the geenii daemon.")
    parser.add_argument("--socket", default=None, help="Unix socket path")
    parser.add_argument("--scheduler-config", default=DEFAULT_SCHEDULER_CONFIG, help="Scheduler config JSON")
    parser.add_argument("--services-config", default=DEFAULT_SERVICES_CONFIG, help="Services config JSON")
    args = parser.parse_args(argv)
    try:
        run_daemon(args.socket, args.scheduler_config, args.services_config)
    except DaemonAlreadyRunning as exc:
        logger.error(str(exc))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
