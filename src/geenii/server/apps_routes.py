"""
HTTP routes for GeeApps, on top of the geenii daemon's `apps.*` methods.

Apps run inside the daemon as supervisor services. Every call sends the
server's app directories (`config.apps_dirs()`, the ones that exist) as
`dirs`, so the daemon also knows this server's project apps.

Reads fall back to scanning the app directories locally when the daemon is
not running (`status` is then null); start/stop/restart/logs/reload need the
daemon.
"""

from __future__ import annotations

import os

import pydantic
from fastapi import APIRouter, Body, Depends, HTTPException, Query

from geenii.apps import AppRegistry
from geenii.config import apps_dirs
from geenii.daemon.client import DaemonClient
from geenii.server.daemon_helper import daemon_call, dep_daemon_client

router = APIRouter(prefix="/apps", tags=["apps"])


class StartAppInput(pydantic.BaseModel):
    model_config = {"extra": "forbid"}

    port: int | None = pydantic.Field(None, ge=1, le=65535, description="Port to serve on; auto-allocated if omitted")


def dep_apps_dirs() -> list[str]:
    return [os.path.abspath(d) for d in apps_dirs() if os.path.isdir(d)]


def _daemon_call(client: DaemonClient, method: str, params: dict, dirs: list[str]):
    """Call the daemon, sending this server's app directories along"""
    return daemon_call(client, method, {**params, "dirs": dirs}, not_found=f"App '{params.get('name')}' not found")


def _local_registry(dirs: list[str]) -> AppRegistry:
    """The apps on disk, for reads without a daemon"""
    registry = AppRegistry(dirs)
    registry.reload()
    return registry


def _offline_info(info: dict) -> dict:
    """Static app info, with the runtime fields the daemon would add left empty"""
    return {**info, "status": None, "pid": None, "uptime_s": None, "failures": 0, "last_exit": None}


@router.get("/")
def list_apps(
    client: DaemonClient = Depends(dep_daemon_client),
    dirs: list[str] = Depends(dep_apps_dirs),
) -> dict:
    """All apps with their runtime status. Without a daemon, the apps on disk with `status: null`."""
    if client.is_available():
        apps = _daemon_call(client, "apps.list", {}, dirs)
        return {"apps": apps, "daemon": {"running": True}}
    apps = sorted(_local_registry(dirs).list(), key=lambda a: a.name)
    return {"apps": [_offline_info(a.info()) for a in apps], "daemon": {"running": False}}


@router.post("/reload")
def reload_apps(
    client: DaemonClient = Depends(dep_daemon_client),
    dirs: list[str] = Depends(dep_apps_dirs),
) -> dict:
    """Rescan the daemon's app directories: `{added, removed, dirs}`."""
    return _daemon_call(client, "apps.reload", {}, dirs)


@router.get("/{name}")
def get_app(
    name: str,
    client: DaemonClient = Depends(dep_daemon_client),
    dirs: list[str] = Depends(dep_apps_dirs),
) -> dict:
    """One app with its runtime status (`status: null` without a daemon)."""
    if client.is_available():
        return _daemon_call(client, "apps.info", {"name": name}, dirs)
    app = _local_registry(dirs).get(name)
    if app is None:
        raise HTTPException(404, f"App '{name}' not found")
    return _offline_info(app.info())


@router.post("/{name}/start")
def start_app(
    name: str,
    body: StartAppInput | None = Body(None),
    client: DaemonClient = Depends(dep_daemon_client),
    dirs: list[str] = Depends(dep_apps_dirs),
) -> dict:
    """Start the app as a daemon service. 409 if it is already started."""
    port = body.port if body else None
    return _daemon_call(client, "apps.start", {"name": name, "port": port}, dirs)


@router.post("/{name}/stop")
def stop_app(
    name: str,
    client: DaemonClient = Depends(dep_daemon_client),
    dirs: list[str] = Depends(dep_apps_dirs),
) -> dict:
    """Stop the app. 409 if it isn't started."""
    return _daemon_call(client, "apps.stop", {"name": name}, dirs)


@router.post("/{name}/restart")
def restart_app(
    name: str,
    body: StartAppInput | None = Body(None),
    client: DaemonClient = Depends(dep_daemon_client),
    dirs: list[str] = Depends(dep_apps_dirs),
) -> dict:
    """Restart the app with its current manifest (starts it if stopped). Keeps its port unless one is given."""
    port = body.port if body else None
    return _daemon_call(client, "apps.restart", {"name": name, "port": port}, dirs)


@router.get("/{name}/logs")
def app_logs(
    name: str,
    tail: int = Query(200, ge=1, le=10000),
    client: DaemonClient = Depends(dep_daemon_client),
    dirs: list[str] = Depends(dep_apps_dirs),
) -> dict:
    """Recent output of the app, as `[tag] line` strings (empty if it never ran)."""
    return {"name": name, "lines": _daemon_call(client, "apps.logs", {"name": name, "tail": tail}, dirs)}
