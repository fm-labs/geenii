"""
ProcessHost: owns the Process Manager, Scheduler, Supervisor and App registry
on one event loop and exposes their operations as namespaced RPC methods.

Method names:
    pm.start, pm.status, pm.output, pm.wait, pm.kill, pm.list, pm.cleanup, pm.gc
    scheduler.status, scheduler.run, scheduler.reload
    supervisor.status, supervisor.ensure, supervisor.start, supervisor.stop, supervisor.restart,
    supervisor.logs, supervisor.reload
    apps.list, apps.info, apps.start, apps.stop, apps.restart, apps.logs, apps.reload,
    apps.set_autostart, apps.set_enabled, apps.add

Apps run as supervisor services named `app-<name>`. Every apps.* method takes
an optional `dirs` list of absolute app directories; new ones are added to the
registry (and scanned) before the call, so a CLI can bring its project's apps.
Apps with autostart (the user's app settings, else the manifest) are started
at start() and when a rescan discovers them; disabled apps can't be started.
apps.set_autostart and apps.set_enabled write the user settings file;
disabling a started app also stops it. apps.add adds an app directory with a
valid manifest by its path, disabled (saved in the user settings).

The pm.* methods are also registered without the prefix (start, status, ...)
for clients of the former standalone process manager service.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import Awaitable, Callable
from typing import Any

from geenii import proc_events
from geenii.apps import AppRegistry, AppStatus, GeeApp, save_app_settings
from geenii.pm.process_manager import ProcessManager
from geenii.scheduler import Scheduler
from geenii.supervisor import MAX_FAILURES, ProcConfig, Supervisor, read_services

logger = logging.getLogger(__name__)

RpcMethod = Callable[[dict], Awaitable[Any]]

# Unprefixed aliases kept for the former `geenii pm serve` protocol
_PM_ALIASES = ("start", "status", "output", "kill", "list", "cleanup")


def _audit(component: proc_events.Component, event: str, params: dict, **fields: Any) -> None:
    """Record a control action in the process event log, with the caller's actor."""
    proc_events.record(component, event, actor=params.get("actor") or "unknown", **fields)


class ProcessHost:
    """The three process components, started and stopped together."""

    def __init__(
        self,
        pm: ProcessManager | None = None,
        scheduler: Scheduler | None = None,
        supervisor: Supervisor | None = None,
        scheduler_config: str | None = None,
        services_config: str | None = None,
        apps: AppRegistry | None = None,
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
        # Apps are scanned at start() and by apps.reload; they run as supervisor services
        self.apps = apps or AppRegistry()
        self._methods: dict[str, RpcMethod] = {
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
            "supervisor.start": self._supervisor_start,
            "supervisor.stop": self._supervisor_stop,
            "supervisor.restart": self._supervisor_restart,
            "supervisor.logs": self._supervisor_logs,
            "supervisor.reload": self._supervisor_reload,
            "apps.list": self._apps_list,
            "apps.info": self._apps_info,
            "apps.start": self._apps_start,
            "apps.stop": self._apps_stop,
            "apps.restart": self._apps_restart,
            "apps.logs": self._apps_logs,
            "apps.reload": self._apps_reload,
            "apps.set_autostart": self._apps_set_autostart,
            "apps.set_enabled": self._apps_set_enabled,
            "apps.add": self._apps_add,
        }
        for name in _PM_ALIASES:
            self._methods[name] = self._methods[f"pm.{name}"]

    @property
    def methods(self) -> dict[str, RpcMethod]:
        return self._methods

    async def start(self) -> None:
        self.pm.recover()
        await asyncio.to_thread(proc_events.prune)
        await asyncio.to_thread(self.apps.reload)
        if self.services_config and os.path.isfile(self.services_config):
            try:
                await self.supervisor.apply_services(read_services(self.services_config))
            except Exception:
                # A broken services file must not keep the daemon from starting
                logger.exception("Could not apply services config %s", self.services_config)
        await self._apps_autostart(self.apps.names())
        await self.scheduler.start()
        logger.info(
            "Process host started (%d scheduled task(s), %d service(s), %d app(s))",
            len(self.scheduler.tasks),
            len(self.supervisor.status()["desired"]),
            len(self.apps.list()),
        )

    async def stop(self) -> None:
        """Stop scheduling first, then supervised processes (including apps), then on-demand processes."""
        await self.scheduler.stop()
        await self.scheduler.wait_until_stopped()
        await self.supervisor.stop()
        await self.pm.shutdown()
        logger.info("Process host stopped")

    async def info(self) -> dict[str, Any]:
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
            "apps": {
                "dirs": self.apps.dirs,
                "count": len(self.apps.list()),
                "running": sum(1 for a in self.apps.list() if a.service_name in sup["running"]),
            },
        }

    # -- pm.* -------------------------------------------------------------------

    async def _pm_start(self, params: dict) -> dict:
        info = await self.pm.start(
            params["command"],
            env=params.get("env"),
            cwd=params.get("cwd") or None,
            pid=params.get("pid") or None,
            origin={"trigger": "manual", "actor": params.get("actor")},
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
        force = params.get("force", False)
        info = await self.pm.kill(params["process_id"], force=force)
        _audit("pm", "pm.kill", params, run_id=info.pid, system_pid=info.system_pid, force=force or None)
        return info.to_dict()

    async def _pm_list(self, params: dict) -> list[dict]:
        procs = await self.pm.list(include_finished=params.get("include_finished", False))
        return [p.to_dict() for p in procs]

    async def _pm_cleanup(self, params: dict) -> str:
        await self.pm.cleanup(params["process_id"])
        _audit("pm", "pm.cleanup", params, run_id=params["process_id"])
        return "ok"

    async def _pm_gc(self, params: dict) -> list[str]:
        removed = await self.pm.gc(
            params.get("max_age"),
            states=params.get("states"),
            dry_run=params.get("dry_run", False),
        )
        if removed and not params.get("dry_run"):
            _audit("pm", "pm.gc", params, removed=len(removed), max_age=params.get("max_age"))
        return removed

    # -- scheduler.* ------------------------------------------------------------

    async def _scheduler_status(self, params: dict) -> dict:
        return self.scheduler.status

    async def _scheduler_run(self, params: dict) -> str:
        await self.scheduler.run_now(params["name"])
        _audit("scheduler", "task.run_now", params, name=params["name"])
        return "started"

    async def _scheduler_reload(self, params: dict) -> dict:
        if not self.scheduler_config:
            raise RuntimeError("The daemon was started without a scheduler config file")
        changes = await self.scheduler.reload_config(self.scheduler_config)
        _audit("scheduler", "config.reload", params, changes=changes)
        return changes

    # -- supervisor.* -----------------------------------------------------------

    async def _supervisor_status(self, params: dict) -> dict:
        return self.supervisor.status()

    async def _supervisor_ensure(self, params: dict) -> str:
        cmd = params.get("cmd")
        if not isinstance(cmd, list) or not cmd or not all(isinstance(a, str) for a in cmd):
            raise ValueError("'cmd' must be a non-empty list of strings")
        name = params["name"]
        await self.supervisor.ensure(
            name,
            ProcConfig(
                name=name,
                cmd=cmd,
                restart=params.get("restart", True),
                env=params.get("env"),
                cwd=params.get("cwd"),
                capture_output=params.get("capture_output", True),
                max_failures=int(params.get("max_failures", MAX_FAILURES)),
            ),
        )
        _audit("supervisor", "service.ensure", params, name=name, cmd=cmd)
        return "ok"

    async def _supervisor_start(self, params: dict) -> str:
        """Start NAME again: a supervised (e.g. stopped with keep) process, or an enabled service of the services file."""
        name = params["name"]
        if name in self.supervisor.status()["desired"]:
            await self.supervisor.restart_process(name)
            _audit("supervisor", "service.start", params, name=name)
            return "ok"
        services = {}
        if self.services_config and os.path.isfile(self.services_config):
            services = {c.name: c for c in read_services(self.services_config)}
        if name not in services:
            raise KeyError(f"'{name}' is not supervised and not an enabled service of the services config")
        await self.supervisor.ensure(name, services[name])
        _audit("supervisor", "service.start", params, name=name)
        return "ok"

    async def _supervisor_stop(self, params: dict) -> str:
        disable_restart = params.get("disable_restart", True)
        await self.supervisor.stop_process(params["name"], disable_restart=disable_restart)
        _audit("supervisor", "service.stop", params, name=params["name"], keep=not disable_restart)
        return "ok"

    async def _supervisor_restart(self, params: dict) -> str:
        await self.supervisor.restart_process(params["name"])
        _audit("supervisor", "service.restart", params, name=params["name"])
        return "ok"

    async def _supervisor_reload(self, params: dict) -> dict:
        if not self.services_config:
            raise RuntimeError("The daemon was started without a services config file")
        if not os.path.isfile(self.services_config):
            raise FileNotFoundError(f"Services config {self.services_config} does not exist")
        changes = await self.supervisor.apply_services(read_services(self.services_config))
        _audit("supervisor", "config.reload", params, changes=changes)
        return changes

    async def _supervisor_logs(self, params: dict) -> list[str]:
        return self.supervisor.logs(params["name"], tail=params.get("tail", 100))

    # -- apps.* -----------------------------------------------------------------

    async def _apps_sync_dirs(self, params: dict) -> None:
        """Add the caller's app directories (absolute paths) and rescan if any is new."""
        dirs = params.get("dirs") or []
        if not isinstance(dirs, list) or not all(isinstance(d, str) and os.path.isabs(d) for d in dirs):
            raise ValueError("'dirs' must be a list of absolute paths")
        if any([self.apps.add_dir(d) for d in dirs]):
            changes = await asyncio.to_thread(self.apps.reload)
            await self._apps_autostart(changes["added"])

    async def _apps_autostart(self, names: list[str]) -> list[str]:
        """Start the apps among NAMES that have autostart and aren't started yet; returns the started ones.

        Errors are logged: one broken app must not keep the daemon or the others from starting.
        """
        started = []
        desired = self.supervisor.status()["desired"]
        for name in names:
            app = self.apps.get(name)
            if app is None or not app.enabled or not app.autostart or app.service_name in desired:
                continue
            try:
                await self._apps_ensure(app, {})
            except Exception:
                logger.exception("Could not autostart app '%s'", name)
                continue
            proc_events.record("supervisor", "app.autostart", actor="daemon", name=name, port=app.port)
            started.append(name)
        if started:
            logger.info("Autostarted app(s): %s", ", ".join(started))
        return started

    async def _apps_get(self, params: dict) -> GeeApp:
        await self._apps_sync_dirs(params)
        return self.apps.require(params["name"])

    def _app_info(self, app: GeeApp, sup: dict | None = None) -> dict:
        """Static app info plus the runtime state of its supervisor service"""
        sup = sup or self.supervisor.status()
        desired = sup["desired"].get(app.service_name)
        rt = sup["running"].get(app.service_name)
        if rt:
            status = AppStatus.RUNNING
        elif desired and (desired.get("gave_up") or desired.get("failures")):
            status = AppStatus.ERROR
        elif desired:
            status = AppStatus.STARTING
        else:
            status = AppStatus.STOPPED
        return {
            **app.info(),
            "status": status.value,
            "pid": rt["pid"] if rt else None,
            "uptime_s": rt["uptime_s"] if rt else None,
            "failures": desired.get("failures", 0) if desired else 0,
            "last_exit": rt["last_exit"] if rt else None,
        }

    async def _apps_ensure(self, app: GeeApp, params: dict) -> None:
        """(Re)define the app's supervisor service from its manifest"""
        port = self.apps.assign_port(app.name, params.get("port"))
        config = app.to_service_config(port=port)
        await self.supervisor.ensure(config.name, config.to_proc_config())

    async def _apps_list(self, params: dict) -> list[dict]:
        await self._apps_sync_dirs(params)
        sup = self.supervisor.status()
        return [self._app_info(app, sup) for app in sorted(self.apps.list(), key=lambda a: a.name)]

    async def _apps_info(self, params: dict) -> dict:
        return self._app_info(await self._apps_get(params))

    @staticmethod
    def _apps_require_enabled(app: GeeApp) -> None:
        if not app.enabled:
            raise RuntimeError(f"App '{app.name}' is disabled; enable it to start it")

    async def _apps_start(self, params: dict) -> dict:
        app = await self._apps_get(params)
        self._apps_require_enabled(app)
        if app.service_name in self.supervisor.status()["desired"]:
            raise RuntimeError(f"App '{app.name}' is already started; use apps.restart to restart it")
        await self._apps_ensure(app, params)
        _audit("supervisor", "app.start", params, name=app.name, port=app.port)
        # deliberately sleep for a sec to wait for the app to start
        time.sleep(1)
        return self._app_info(app)

    async def _apps_stop(self, params: dict) -> dict:
        app = await self._apps_get(params)
        if app.service_name not in self.supervisor.status()["desired"]:
            raise RuntimeError(f"App '{app.name}' is not running")
        await self.supervisor.stop_process(app.service_name, disable_restart=True)
        _audit("supervisor", "app.stop", params, name=app.name)
        return self._app_info(app)

    async def _apps_restart(self, params: dict) -> dict:
        """Restart with a fresh service config, so manifest changes take effect (starts a stopped app)"""
        app = await self._apps_get(params)
        self._apps_require_enabled(app)
        await self._apps_ensure(app, params)
        await self.supervisor.restart_process(app.service_name)
        _audit("supervisor", "app.restart", params, name=app.name, port=app.port)
        return self._app_info(app)

    async def _apps_logs(self, params: dict) -> list[str]:
        app = await self._apps_get(params)
        try:
            return self.supervisor.logs(app.service_name, tail=params.get("tail", 100))
        except KeyError:
            return []  # never started since the daemon started

    async def _apps_reload(self, params: dict) -> dict:
        await self._apps_sync_dirs(params)
        changes = await asyncio.to_thread(self.apps.reload)
        autostarted = await self._apps_autostart(changes["added"])
        return {**changes, "autostarted": autostarted, "dirs": self.apps.dirs}

    async def _apps_set_setting(self, params: dict, field: str) -> dict:
        """Set a boolean FIELD of the app's user settings (in the user settings file).

        Autostart applies at the next daemon start; the app isn't started or stopped.
        """
        app = await self._apps_get(params)
        value = params.get(field)
        if not isinstance(value, bool):
            raise ValueError(f"'{field}' must be true or false")
        app.settings = await asyncio.to_thread(save_app_settings, app.path, **{field: value})
        _audit("supervisor", f"app.set_{field}", params, name=app.name, **{field: value})
        return self._app_info(app)

    async def _apps_set_autostart(self, params: dict) -> dict:
        return await self._apps_set_setting(params, "autostart")

    async def _apps_add(self, params: dict) -> dict:
        """Add the app directory `path` (it needs a valid manifest), disabled"""
        await self._apps_sync_dirs(params)
        path = params.get("path")
        if not isinstance(path, str) or not path.strip():
            raise ValueError("'path' must be a directory path")
        if not os.path.isabs(os.path.expanduser(path.strip())):
            raise ValueError(f"'path' must be absolute: {path}")
        app = await asyncio.to_thread(self.apps.add_app, path.strip())
        _audit("supervisor", "app.add", params, name=app.name, path=app.path)
        return self._app_info(app)

    async def _apps_set_enabled(self, params: dict) -> dict:
        """Enable or disable the app; disabling also stops it if it is started"""
        info = await self._apps_set_setting(params, "enabled")
        app = self.apps.require(params["name"])
        if not app.enabled and app.service_name in self.supervisor.status()["desired"]:
            await self.supervisor.stop_process(app.service_name, disable_restart=True)
            _audit("supervisor", "app.stop", params, name=app.name, reason="disabled")
            info = self._app_info(app)
        return info
