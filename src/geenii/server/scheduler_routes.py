"""
HTTP routes for viewing and editing the scheduler config.

Works on the scheduler config file: the one the running daemon was started with,
or the default .geenii/scheduler.json. Reads add the live state of each task
(next/last run, running) when the daemon is running; writes update the file and
make a daemon that uses it reload, like `geenii scheduler add/remove`.
"""

from __future__ import annotations

import json
import os
import tempfile
import threading

import pydantic
from fastapi import APIRouter, Depends, HTTPException

from geenii.daemon.client import DaemonClient
from geenii.scheduler import SchedulerConfig, parse_interval
from geenii.server.daemon_routes import dep_daemon_client

router = APIRouter(prefix="/scheduler", tags=["scheduler"])

# Serializes read-modify-write of the config file within this server
_write_lock = threading.Lock()

# Fields the editor manages; other keys of an existing entry are kept on update
_TASK_FIELDS = set(SchedulerConfig.model_fields)


def default_scheduler_config() -> str:
    # Imported lazily: geenii.daemon.server pulls in the scheduler and supervisor
    from geenii.daemon.server import DEFAULT_SCHEDULER_CONFIG

    return DEFAULT_SCHEDULER_CONFIG


def dep_scheduler_config_path() -> str:
    return default_scheduler_config()


class TaskInput(pydantic.BaseModel):
    """A scheduled task as sent by the editor. Use either `cmd` or `module`."""

    model_config = {"extra": "forbid"}

    name: str = pydantic.Field(..., min_length=1)
    interval: str = pydantic.Field(..., description="'cron:EXPRESSION' or 'at:ISO-DATETIME'")
    cmd: list[str] | None = None
    module: str | None = None
    params: list[str] | None = None
    env: dict[str, str] | None = None
    working_dir: str | None = None
    timeout: float | None = pydantic.Field(None, gt=0)
    allow_overlap: bool = False
    enabled: bool = True

    def to_entry(self) -> dict:
        """The config file entry, with empty optional fields left out (as `geenii scheduler add` writes it)."""
        entry: dict = {"enabled": self.enabled, "name": self.name.strip(), "interval": self.interval.strip()}
        if self.cmd:
            entry["cmd"] = self.cmd
        if self.module:
            entry["module"] = self.module.strip()
            if self.params:
                entry["params"] = self.params
        if self.env:
            entry["env"] = self.env
        if self.working_dir and self.working_dir.strip():
            entry["working_dir"] = self.working_dir.strip()
        if self.timeout is not None:
            entry["timeout"] = self.timeout
        if self.allow_overlap:
            entry["allow_overlap"] = True
        return entry


def _validate(task: TaskInput) -> None:
    """Checks the scheduler would otherwise only log when loading the file. Raises HTTPException(400)."""
    if not task.name.strip():
        raise HTTPException(400, "Name must not be empty")
    try:
        parse_interval(task.interval.strip())
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    has_cmd = bool(task.cmd and any(a.strip() for a in task.cmd))
    has_module = bool(task.module and task.module.strip())
    if has_cmd == has_module:
        raise HTTPException(400, "Set either a command or a module, not both")
    if has_module and "." not in task.module.strip():
        raise HTTPException(400, f"Module path '{task.module}' must include at least one dot, e.g. pkg.function")


def _daemon_state(client: DaemonClient) -> tuple[dict | None, str | None, str | None]:
    """(scheduler status, config path the daemon uses, error) — status is None when the daemon is unreachable."""
    if not client.is_available():
        return None, None, None
    try:
        config = client.info()["scheduler"].get("config")
        return client.call("scheduler.status"), config, None
    except (RuntimeError, OSError, KeyError) as exc:
        return None, None, str(exc)


def _config_path(client: DaemonClient, default_path: str) -> tuple[str, bool]:
    """(config path to edit, whether a running daemon schedules it)."""
    if client.is_available():
        try:
            daemon_config = client.info()["scheduler"].get("config")
        except RuntimeError, OSError, KeyError:
            daemon_config = None
        if daemon_config:
            return daemon_config, True
    return default_path, False


def _read(path: str) -> dict:
    if not os.path.isfile(path):
        return {"tasks": []}
    try:
        with open(path) as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        raise HTTPException(409, f"Could not read {path}: {exc}")
    if not isinstance(data, dict) or not isinstance(data.setdefault("tasks", []), list):
        raise HTTPException(409, f"{path} is not a scheduler config (expected an object with a 'tasks' list)")
    return data


def _write(path: str, data: dict) -> None:
    """Write atomically, so the daemon never reads a half-written file."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".scheduler-", suffix=".json", dir=directory)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp, path)
    except BaseException:
        os.unlink(tmp)
        raise


def _index(tasks: list, name: str) -> int | None:
    return next((i for i, t in enumerate(tasks) if isinstance(t, dict) and t.get("name") == name), None)


def _reload(client: DaemonClient, live: bool) -> dict:
    """Make the daemon re-read the file if it schedules it; the file change stands either way."""
    if not live:
        return {"reloaded": False, "changes": None, "error": None}
    try:
        return {"reloaded": True, "changes": client.call("scheduler.reload"), "error": None}
    except (RuntimeError, OSError) as exc:
        return {"reloaded": False, "changes": None, "error": str(exc)}


@router.get("/config")
def get_scheduler_config(
    client: DaemonClient = Depends(dep_daemon_client),
    default_path: str = Depends(dep_scheduler_config_path),
) -> dict:
    """The scheduler config file's tasks, including disabled ones, with live state from the daemon.

    `tasks[].live` is null for tasks the running scheduler has not loaded (disabled,
    invalid, or the daemon is not running / uses another config file).
    """
    status, daemon_config, daemon_error = _daemon_state(client)
    path = daemon_config or default_path

    result: dict = {
        "path": path,
        "exists": os.path.isfile(path),
        "daemon": {
            "running": status is not None,
            "config": daemon_config,
            "status": status["status"] if status else None,
            "error": daemon_error,
        },
        "tasks": [],
        "error": None,
    }

    raw_tasks: list = []
    if result["exists"]:
        try:
            raw_tasks = _read(path)["tasks"]
        except HTTPException as exc:
            result["error"] = exc.detail

    live = {t["name"]: t for t in status["tasks"]} if status else {}
    seen: set[str] = set()
    for entry in raw_tasks:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        task = dict(entry)
        task.setdefault("enabled", True)
        # A duplicate name is skipped by the scheduler, so only the first entry gets the live state
        task["live"] = live.get(name) if name not in seen else None
        seen.add(name)
        result["tasks"].append(task)

    # Tasks the daemon runs that are not in the file (added at runtime, or the file changed since)
    for name, t in live.items():
        if name not in seen:
            result["tasks"].append(
                {
                    "name": name,
                    "interval": t["interval"],
                    "cmd": t["cmd"],
                    "module": t["module"] or "",
                    "enabled": t["enabled"],
                    "live": t,
                    "not_in_config": True,
                }
            )
    return result


@router.post("/tasks", status_code=201)
def create_task(
    task: TaskInput,
    client: DaemonClient = Depends(dep_daemon_client),
    default_path: str = Depends(dep_scheduler_config_path),
) -> dict:
    """Add a task to the scheduler config."""
    _validate(task)
    path, live = _config_path(client, default_path)
    entry = task.to_entry()
    with _write_lock:
        data = _read(path)
        if _index(data["tasks"], entry["name"]) is not None:
            raise HTTPException(409, f"Task '{entry['name']}' already exists")
        data["tasks"].append(entry)
        _write(path, data)
    return {"task": entry, "path": path, "reload": _reload(client, live)}


@router.put("/tasks/{name}")
def update_task(
    name: str,
    task: TaskInput,
    client: DaemonClient = Depends(dep_daemon_client),
    default_path: str = Depends(dep_scheduler_config_path),
) -> dict:
    """Replace a task in the scheduler config. `task.name` may differ from `name` to rename it."""
    _validate(task)
    path, live = _config_path(client, default_path)
    new_entry = task.to_entry()
    with _write_lock:
        data = _read(path)
        i = _index(data["tasks"], name)
        if i is None:
            raise HTTPException(404, f"Task '{name}' not found in {path}")
        if new_entry["name"] != name and _index(data["tasks"], new_entry["name"]) is not None:
            raise HTTPException(409, f"Task '{new_entry['name']}' already exists")
        # Keep keys the editor does not know about
        extra = {k: v for k, v in data["tasks"][i].items() if k not in _TASK_FIELDS}
        data["tasks"][i] = {**new_entry, **extra}
        _write(path, data)
    return {"task": data["tasks"][i], "path": path, "reload": _reload(client, live)}


@router.delete("/tasks/{name}")
def delete_task(
    name: str,
    client: DaemonClient = Depends(dep_daemon_client),
    default_path: str = Depends(dep_scheduler_config_path),
) -> dict:
    """Remove a task from the scheduler config. A run already in progress is allowed to finish."""
    path, live = _config_path(client, default_path)
    with _write_lock:
        if not os.path.isfile(path):
            raise HTTPException(404, f"Config file not found: {path}")
        data = _read(path)
        i = _index(data["tasks"], name)
        if i is None:
            raise HTTPException(404, f"Task '{name}' not found in {path}")
        del data["tasks"][i]
        _write(path, data)
    return {"path": path, "reload": _reload(client, live)}


@router.post("/tasks/{name}/run", status_code=202)
def run_task(
    name: str,
    client: DaemonClient = Depends(dep_daemon_client),
    default_path: str = Depends(dep_scheduler_config_path),
) -> dict:
    """Start a run of a task in the running daemon right away, outside its schedule.

    Returns once the run has started; its state shows up in GET /scheduler/config
    (`live.running`, `live.last_run_id` for the process manager).
    """
    path, live = _config_path(client, default_path)
    if not live:
        raise HTTPException(409, "The geenii daemon is not running a scheduler (start it with `geenii daemon start`)")
    try:
        client.call("scheduler.run", {"name": name})
    except RuntimeError as exc:
        # Daemon errors are "<ExceptionType>: <message>"
        exc_type, _, detail = str(exc).partition(": ")
        if exc_type == "KeyError":
            raise HTTPException(404, f"Task '{name}' is not loaded in the running scheduler (disabled or invalid?)")
        raise HTTPException(409, detail or str(exc))
    except OSError as exc:
        raise HTTPException(503, f"The geenii daemon is not reachable: {exc}")
    return {"name": name, "status": "started", "path": path}
