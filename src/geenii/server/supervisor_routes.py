"""
HTTP routes for viewing and editing the supervisor's services and controlling them.

Works on the services config file: the one the running daemon was started with,
or the default .geenii/services.json. Reads add the live state of each service
(running, pid, uptime, ...) when the daemon is running; writes update the file and
make a daemon that uses it reload, like `geenii supervisor add/remove`.
Start/stop/restart/logs act on the running daemon only.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading

import pydantic
from fastapi import APIRouter, Depends, HTTPException, Query

from geenii.daemon.client import DaemonClient
from geenii.server.daemon_routes import dep_daemon_client
from geenii.supervisor import ServiceConfig

router = APIRouter(prefix="/supervisor", tags=["supervisor"])

# Serializes read-modify-write of the config file within this server
_write_lock = threading.Lock()

# Fields the editor manages; other keys of an existing entry are kept on update
_SERVICE_FIELDS = set(ServiceConfig.model_fields)


def default_services_config() -> str:
    # Imported lazily: geenii.daemon.server pulls in the scheduler and supervisor
    from geenii.daemon.server import DEFAULT_SERVICES_CONFIG

    return DEFAULT_SERVICES_CONFIG


def dep_services_config_path() -> str:
    return default_services_config()


class ServiceInput(pydantic.BaseModel):
    """A service as sent by the editor."""

    model_config = {"extra": "forbid"}

    name: str = pydantic.Field(..., min_length=1)
    cmd: list[str] = pydantic.Field(..., min_length=1)
    restart: bool = True
    env: dict[str, str] | None = None
    cwd: str | None = None
    capture_output: bool = True
    enabled: bool = True

    def to_entry(self) -> dict:
        """The config file entry, with default values left out (as `geenii supervisor add` writes it)."""
        entry: dict = {"name": self.name.strip(), "cmd": self.cmd}
        if not self.restart:
            entry["restart"] = False
        if self.env:
            entry["env"] = self.env
        if self.cwd and self.cwd.strip():
            entry["cwd"] = self.cwd.strip()
        if not self.capture_output:
            entry["capture_output"] = False
        if not self.enabled:
            entry["enabled"] = False
        return entry


def _validate(service: ServiceInput) -> None:
    if not service.name.strip():
        raise HTTPException(400, "Name must not be empty")
    if not service.cmd[0].strip():
        raise HTTPException(400, "The command must not be empty")


def _live_state(status: dict, name: str) -> dict | None:
    """The supervisor's state of NAME, or None when it is not supervised."""
    desired = status["desired"].get(name)
    if desired is None:
        return None
    running = status["running"].get(name)
    watcher = status["watchers"].get(name)
    if running and running.get("returncode") is None:
        state = "running"
    elif watcher and not watcher["done"]:
        # Waiting out the restart delay, or (re)spawning
        state = "restarting"
    else:
        # Stopped with keep, or exited without restart
        state = "stopped"
    return {
        "state": state,
        "source": desired["source"],
        "pid": running["pid"] if running else None,
        "uptime_s": running["uptime_s"] if running else None,
        "backoff_s": running["backoff_s"] if running else None,
        "last_exit": running["last_exit"] if running else None,
        "restart": desired["restart"],
    }


def _daemon_state(client: DaemonClient) -> tuple[dict | None, str | None, str | None]:
    """(supervisor status, config path the daemon uses, error) — status is None when the daemon is unreachable."""
    if not client.is_available():
        return None, None, None
    try:
        config = client.info()["supervisor"].get("config")
        return client.call("supervisor.status"), config, None
    except (RuntimeError, OSError, KeyError) as exc:
        return None, None, str(exc)


def _config_path(client: DaemonClient, default_path: str) -> tuple[str, bool]:
    """(config path to edit, whether a running daemon applies it)."""
    if client.is_available():
        try:
            daemon_config = client.info()["supervisor"].get("config")
        except RuntimeError, OSError, KeyError:
            daemon_config = None
        if daemon_config:
            return daemon_config, True
    return default_path, False


def _read(path: str) -> dict:
    if not os.path.isfile(path):
        return {"services": []}
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        raise HTTPException(409, f"Could not read {path}: {exc}")
    if not isinstance(data, dict) or not isinstance(data.setdefault("services", []), list):
        raise HTTPException(409, f"{path} is not a services config (expected an object with a 'services' list)")
    return data


def _write(path: str, data: dict) -> None:
    """Write atomically, so the daemon never reads a half-written file."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".services-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def _index(services: list, name: str) -> int | None:
    return next((i for i, s in enumerate(services) if isinstance(s, dict) and s.get("name") == name), None)


def _reload(client: DaemonClient, live: bool) -> dict:
    """Make the daemon re-apply the file if it uses it; the file change stands either way."""
    if not live:
        return {"reloaded": False, "changes": None, "error": None}
    try:
        return {"reloaded": True, "changes": client.call("supervisor.reload"), "error": None}
    except (RuntimeError, OSError) as exc:
        return {"reloaded": False, "changes": None, "error": str(exc)}


def _daemon_call(client: DaemonClient, method: str, params: dict):
    """Call the running daemon, mapping its errors to HTTP errors."""
    if not client.is_available():
        raise HTTPException(409, "The geenii daemon is not running (start it with `geenii daemon start`)")
    try:
        return client.call(method, params)
    except RuntimeError as exc:
        # Daemon errors are "<ExceptionType>: <message>"
        exc_type, _, detail = str(exc).partition(": ")
        if exc_type == "KeyError":
            raise HTTPException(404, f"'{params.get('name')}' is not supervised by the running daemon")
        raise HTTPException(409, detail or str(exc))
    except OSError as exc:
        raise HTTPException(503, f"The geenii daemon is not reachable: {exc}")


@router.get("/config")
def get_supervisor_config(
    client: DaemonClient = Depends(dep_daemon_client),
    default_path: str = Depends(dep_services_config_path),
) -> dict:
    """The services config file's services, including disabled ones, with live state from the daemon.

    `services[].live` is null for services the running supervisor does not supervise
    (disabled, invalid, stopped, or the daemon is not running). Services the daemon
    supervises that are not in the file (`geenii supervisor start`) are appended
    with `not_in_config: true`.
    """
    status, daemon_config, daemon_error = _daemon_state(client)
    path = daemon_config or default_path

    result: dict = {
        "path": path,
        "exists": os.path.isfile(path),
        "daemon": {
            "running": status is not None,
            "config": daemon_config,
            "error": daemon_error,
        },
        "services": [],
        "error": None,
    }

    raw: list = []
    if result["exists"]:
        try:
            raw = _read(path)["services"]
        except HTTPException as exc:
            result["error"] = exc.detail

    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        service = dict(entry)
        service.setdefault("enabled", True)
        service.setdefault("restart", True)
        # A duplicate name is skipped by the daemon, so only the first entry gets the live state
        service["live"] = _live_state(status, name) if status and name not in seen else None
        seen.add(name)
        result["services"].append(service)

    if status:
        for name, desired in status["desired"].items():
            if name not in seen:
                result["services"].append(
                    {
                        "name": name,
                        "cmd": desired["cmd"],
                        "restart": desired["restart"],
                        "cwd": desired["cwd"],
                        "enabled": True,
                        "live": _live_state(status, name),
                        "not_in_config": True,
                    }
                )
    return result


@router.post("/services", status_code=201)
def create_service(
    service: ServiceInput,
    client: DaemonClient = Depends(dep_daemon_client),
    default_path: str = Depends(dep_services_config_path),
) -> dict:
    """Add a service to the services config; a running daemon that uses the file starts it."""
    _validate(service)
    path, live = _config_path(client, default_path)
    entry = service.to_entry()
    with _write_lock:
        data = _read(path)
        if _index(data["services"], entry["name"]) is not None:
            raise HTTPException(409, f"Service '{entry['name']}' already exists")
        data["services"].append(entry)
        _write(path, data)
    return {"service": entry, "path": path, "reload": _reload(client, live)}


@router.put("/services/{name}")
def update_service(
    name: str,
    service: ServiceInput,
    client: DaemonClient = Depends(dep_daemon_client),
    default_path: str = Depends(dep_services_config_path),
) -> dict:
    """Replace a service in the services config (a running daemon restarts it). `service.name` may differ to rename it."""
    _validate(service)
    path, live = _config_path(client, default_path)
    new_entry = service.to_entry()
    with _write_lock:
        data = _read(path)
        i = _index(data["services"], name)
        if i is None:
            raise HTTPException(404, f"Service '{name}' not found in {path}")
        if new_entry["name"] != name and _index(data["services"], new_entry["name"]) is not None:
            raise HTTPException(409, f"Service '{new_entry['name']}' already exists")
        # Keep keys the editor does not know about
        extra = {k: v for k, v in data["services"][i].items() if k not in _SERVICE_FIELDS}
        data["services"][i] = {**new_entry, **extra}
        _write(path, data)
    return {"service": data["services"][i], "path": path, "reload": _reload(client, live)}


@router.delete("/services/{name}")
def delete_service(
    name: str,
    client: DaemonClient = Depends(dep_daemon_client),
    default_path: str = Depends(dep_services_config_path),
) -> dict:
    """Remove a service from the services config; a running daemon that uses the file stops it."""
    path, live = _config_path(client, default_path)
    with _write_lock:
        if not os.path.isfile(path):
            raise HTTPException(404, f"Config file not found: {path}")
        data = _read(path)
        i = _index(data["services"], name)
        if i is None:
            raise HTTPException(404, f"Service '{name}' not found in {path}")
        del data["services"][i]
        _write(path, data)
    return {"path": path, "reload": _reload(client, live)}


@router.post("/services/{name}/start")
def start_service(name: str, client: DaemonClient = Depends(dep_daemon_client)) -> dict:
    """Start a stopped service in the running daemon (a supervised one, or an enabled one of its config file)."""
    _daemon_call(client, "supervisor.start", {"name": name})
    return {"name": name, "status": "started"}


@router.post("/services/{name}/stop")
def stop_service(name: str, client: DaemonClient = Depends(dep_daemon_client)) -> dict:
    """Stop a service in the running daemon. It stays listed as stopped until started or the daemon restarts."""
    _daemon_call(client, "supervisor.stop", {"name": name, "disable_restart": False})
    return {"name": name, "status": "stopped"}


@router.post("/services/{name}/restart")
def restart_service(name: str, client: DaemonClient = Depends(dep_daemon_client)) -> dict:
    """Restart a service in the running daemon now (also resets its restart backoff)."""
    _daemon_call(client, "supervisor.restart", {"name": name})
    return {"name": name, "status": "restarted"}


@router.get("/services/{name}/logs")
def service_logs(
    name: str,
    tail: int = Query(200, ge=1, le=10000),
    client: DaemonClient = Depends(dep_daemon_client),
) -> dict:
    """Recent output of a service: stdout, stderr and supervisor events, as `[tag] line` strings."""
    return {"name": name, "lines": _daemon_call(client, "supervisor.logs", {"name": name, "tail": tail})}
