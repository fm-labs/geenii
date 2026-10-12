"""
ProcessHost: owns the Process Manager, Scheduler and Supervisor on one event
loop and exposes their operations as namespaced RPC methods.

Method names:
    pm.start, pm.status, pm.output, pm.wait, pm.kill, pm.list, pm.cleanup, pm.gc
    scheduler.status, scheduler.run, scheduler.reload
    supervisor.status, supervisor.ensure, supervisor.stop, supervisor.restart, supervisor.logs,
    supervisor.reload

The pm.* methods are also registered without the prefix (start, status, ...)
for clients of the former standalone process manager service.
"""
from __future__ import annotations

import logging
import os
from typing import Any, Awaitable, Callable, Dict, Optional

from geenii.pm.process_manager import ProcessManager
from geenii.scheduler import Scheduler
from geenii.supervisor import ProcConfig, Supervisor, read_services

logger = logging.getLogger(__name__)

RpcMethod = Callable[[dict], Awaitable[Any]]

# Unprefixed aliases kept for the former `geenii pm serve` protocol
_PM_ALIASES = ("start", "status", "output", "kill", "list", "cleanup")


class ProcessHost:
    """The three process components, started and stopped together."""

    def __init__(
        self,
        pm: Optional[ProcessManager] = None,
        scheduler: Optional[Scheduler] = None,
        supervisor: Optional[Supervisor] = None,
        scheduler_config: Optional[str] = None,
        services_config: Optional[str] = None,
    ) -> None:
        self.pm = pm or ProcessManager()
        self.scheduler = scheduler or Scheduler()
        # Scheduled commands run as process-manager processes of this host
        self.scheduler.pm = self.pm
        self.supervisor = supervisor or Supervisor()
        # The file scheduler.reload re-reads (the one the scheduler was loaded from)
        self.scheduler_config = os.path.abspath(scheduler_config) if scheduler_config else None
        # The services file applied at start() and by supervisor.reload
        self.services_config = os.path.abspath(services_config) if services_config else None
        self._methods: Dict[str, RpcMethod] = {
            "pm.start": self._pm_start,
            "pm.status": self._pm_status,
            "pm.output": self._pm_output,
            "pm.wait": self._pm_wait,
            "pm.kill": self._pm_kill,
            "pm.list": self._pm_list,
            "pm.cleanup": self._pm_cleanup,
            "pm.gc": self._pm_gc,
            "scheduler.status": self._scheduler_status,
            "scheduler.run": self._scheduler_run,
            "scheduler.reload": self._scheduler_reload,
            "supervisor.status": self._supervisor_status,
            "supervisor.ensure": self._supervisor_ensure,
            "supervisor.stop": self._supervisor_stop,
            "supervisor.restart": self._supervisor_restart,
            "supervisor.logs": self._supervisor_logs,
            "supervisor.reload": self._supervisor_reload,
        }
        for name in _PM_ALIASES:
            self._methods[name] = self._methods[f"pm.{name}"]

    @property
    def methods(self) -> Dict[str, RpcMethod]:
        return self._methods

    async def start(self) -> None:
        self.pm.recover()
        if self.services_config and os.path.isfile(self.services_config):
            try:
                await self.supervisor.apply_services(read_services(self.services_config))
            except Exception:
                # A broken services file must not keep the daemon from starting
                logger.exception("Could not apply services config %s", self.services_config)
        await self.scheduler.start()
        logger.info("Process host started (%d scheduled task(s), %d service(s))",
                    len(self.scheduler.tasks), len(self.supervisor.status()["desired"]))

    async def stop(self) -> None:
        """Stop scheduling first, then supervised processes, then on-demand processes."""
        await self.scheduler.stop()
        await self.scheduler.wait_until_stopped()
        await self.supervisor.stop()
        await self.pm.shutdown()
        logger.info("Process host stopped")

    async def info(self) -> Dict[str, Any]:
        sup = self.supervisor.status()
        return {
            "pm": {"running": len(await self.pm.list())},
            "scheduler": {
                "status": self.scheduler.status["status"],
                "config": self.scheduler_config,
                "tasks": len(self.scheduler.tasks),
                "running_tasks": self.scheduler.status["running_tasks"],
            },
            "supervisor": {
                "config": self.services_config,
                "desired": len(sup["desired"]),
                "running": len(sup["running"]),
            },
        }

    # -- pm.* -------------------------------------------------------------------

    async def _pm_start(self, params: dict) -> dict:
        info = await self.pm.start(
            params["command"],
            env=params.get("env"),
            cwd=params.get("cwd") or None,
            pid=params.get("pid") or None,
        )
        return info.to_dict()

    async def _pm_status(self, params: dict) -> dict:
        return (await self.pm.status(params["process_id"])).to_dict()

    async def _pm_output(self, params: dict) -> str:
        tail = params.get("tail")
        return await self.pm.output(
            params["process_id"],
            stream=params.get("stream", "stdout"),
            tail=tail if tail and tail > 0 else None,
            offset=params.get("offset"),
            limit=params.get("limit"),
        )

    async def _pm_wait(self, params: dict) -> dict:
        return (await self.pm.wait(params["process_id"], timeout=params.get("timeout"))).to_dict()

    async def _pm_kill(self, params: dict) -> dict:
        return (await self.pm.kill(params["process_id"], force=params.get("force", False))).to_dict()

    async def _pm_list(self, params: dict) -> list[dict]:
        procs = await self.pm.list(include_finished=params.get("include_finished", False))
        return [p.to_dict() for p in procs]

    async def _pm_cleanup(self, params: dict) -> str:
        await self.pm.cleanup(params["process_id"])
        return "ok"

    async def _pm_gc(self, params: dict) -> list[str]:
        return await self.pm.gc(
            params.get("max_age"),
            states=params.get("states"),
            dry_run=params.get("dry_run", False),
        )

    # -- scheduler.* ------------------------------------------------------------

    async def _scheduler_status(self, params: dict) -> dict:
        return self.scheduler.status

    async def _scheduler_run(self, params: dict) -> str:
        await self.scheduler.run_now(params["name"])
        return "started"

    async def _scheduler_reload(self, params: dict) -> dict:
        if not self.scheduler_config:
            raise RuntimeError("The daemon was started without a scheduler config file")
        return await self.scheduler.reload_config(self.scheduler_config)

    # -- supervisor.* -----------------------------------------------------------

    async def _supervisor_status(self, params: dict) -> dict:
        return self.supervisor.status()

    async def _supervisor_ensure(self, params: dict) -> str:
        cmd = params.get("cmd")
        if not isinstance(cmd, list) or not cmd or not all(isinstance(a, str) for a in cmd):
            raise ValueError("'cmd' must be a non-empty list of strings")
        name = params["name"]
        await self.supervisor.ensure(name, ProcConfig(
            name=name,
            cmd=cmd,
            restart=params.get("restart", True),
            env=params.get("env"),
            cwd=params.get("cwd"),
            capture_output=params.get("capture_output", True),
        ))
        return "ok"

    async def _supervisor_stop(self, params: dict) -> str:
        await self.supervisor.stop_process(params["name"], disable_restart=params.get("disable_restart", True))
        return "ok"

    async def _supervisor_restart(self, params: dict) -> str:
        await self.supervisor.restart_process(params["name"])
        return "ok"

    async def _supervisor_reload(self, params: dict) -> dict:
        if not self.services_config:
            raise RuntimeError("The daemon was started without a services config file")
        if not os.path.isfile(self.services_config):
            raise FileNotFoundError(f"Services config {self.services_config} does not exist")
        return await self.supervisor.apply_services(read_services(self.services_config))

    async def _supervisor_logs(self, params: dict) -> list[str]:
        return self.supervisor.logs(params["name"], tail=params.get("tail", 100))
