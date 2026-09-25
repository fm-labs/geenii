"""
Simple task scheduler.

Reads task definitions from a JSON config file. Each task specifies an
interval (cron expression or fixed datetime) and a command to execute.

Config file format (scheduler.json):
    {
        "tasks": [
            {
                "enabled": true,
                "name": "geenii_cleanup",
                "interval": "cron:0 * * * *",
                "cmd": ["$GEENII_BIN", "tasks", "exec", "cleanup"],
                "env": {"CLEANUP_DRY_RUN": "true"},
                "timeout": 600
            }
        ]
    }

Interval formats:
    "cron:EXPRESSION"   – recurring cron schedule, e.g. "cron:*/5 * * * *"
    "at:DATETIME"       – one-shot execution at an ISO datetime, e.g. "at:2026-07-21T18:00:00Z"

`cmd` tasks run as process-manager processes: every run gets a process ID
("<task>-<UTC timestamp>-<random>"), its output is saved to disk, and the last
RUNS_KEPT_PER_TASK finished runs of each task are kept.
"""
from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import logging
import os
import re
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pydantic
from croniter import croniter

from geenii.pm.process_manager import ProcessManager, ProcessState

logger = logging.getLogger(__name__)

RUNS_KEPT_PER_TASK = 10  # finished runs (process records + logs) kept per cmd task


def parse_interval(interval: str) -> tuple[str, str]:
    """Parse an interval string into (kind, value). Raises ValueError on bad format."""
    if interval.startswith("cron:"):
        expr = interval[5:].strip()
        if not croniter.is_valid(expr):
            raise ValueError(f"Invalid cron expression: {expr}")
        return "cron", expr
    elif interval.startswith("at:"):
        dt_str = interval[3:].strip()
        datetime.fromisoformat(dt_str)
        return "at", dt_str
    else:
        raise ValueError(f"Invalid interval format: {interval!r}. Must start with 'cron:' or 'at:'")


def _accepts_params_env(fn: Callable) -> bool:
    """True if fn can be called as fn(params, env); False if it only takes no arguments."""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return False
    try:
        sig.bind([], None)
        return True
    except TypeError:
        pass
    sig.bind()  # raises TypeError if fn needs arguments we cannot provide
    return False


@dataclass
class ScheduledTask:
    """A single scheduled task."""

    name: str
    interval: str
    cmd: list[str] | None = None
    module: str = ""
    run_fn: Callable[..., Any] | None = field(default=None, repr=False)
    params: list[str] | None = None     # passed to module/run_fn callables as fn(params, env)
    enabled: bool = True
    env: dict[str, str] | None = None
    working_dir: Path | None = None
    timeout: float | None = None        # seconds; the run is cancelled (and its process killed) when exceeded
    allow_overlap: bool = False         # start a new run even if the previous one is still running
    last_run_id: str | None = field(default=None, init=False)  # process ID of the latest cmd run
    _pass_args: bool = field(default=False, init=False, repr=False)

    def load(self) -> None:
        """Validate interval and resolve execution target (cmd or module)."""
        parse_interval(self.interval)

        if self.cmd:
            return
        if self.run_fn is None:
            if not self.module:
                raise ValueError("Task must have 'cmd', 'module', or 'run_fn' set")
            parts = self.module.split(".")
            if len(parts) < 2:
                raise ValueError(f"Module path '{self.module}' must include at least one dot")
            module_name = ".".join(parts[:-1])
            fn_name = parts[-1]
            mod = importlib.import_module(module_name)
            fn = getattr(mod, fn_name, None)
            if fn is None or not callable(fn):
                raise AttributeError(f"Module '{self.module}' does not export a callable '{fn_name}'")
            self.run_fn = fn
        self._pass_args = _accepts_params_env(self.run_fn)

    @property
    def is_oneshot(self) -> bool:
        return self.interval.startswith("at:")

    def next_run(self, after: datetime | None = None) -> datetime:
        """Return the next execution time as a UTC datetime."""
        kind, value = parse_interval(self.interval)
        if kind == "at":
            return datetime.fromisoformat(value).astimezone(timezone.utc)
        base = after or datetime.now(timezone.utc)
        return croniter(value, base).get_next(datetime).replace(tzinfo=timezone.utc)

    async def run(self, pm: ProcessManager | None = None) -> None:
        """Run the task: cmd as a process of pm, or the Python callable (run_fn).

        Failures and timeouts are logged, not raised. Cancellation propagates.
        Raises ValueError if a cmd task is run without a ProcessManager.
        """
        if self.cmd and pm is None:
            raise ValueError(f"Task '{self.name}' runs a command and needs a ProcessManager")
        logger.info("Running task '%s'", self.name)
        try:
            await asyncio.wait_for(self._execute(pm), timeout=self.timeout)
            logger.info("Task '%s' completed successfully", self.name)
        except asyncio.TimeoutError:
            logger.error("Task '%s' timed out after %ss", self.name, self.timeout)
        except Exception:
            logger.exception("Task '%s' failed", self.name)

    async def _execute(self, pm: ProcessManager | None) -> None:
        if self.cmd:
            await self._run_cmd(pm)
        elif self.run_fn is not None:
            args = (self.params or [], self.env) if self._pass_args else ()
            if inspect.iscoroutinefunction(self.run_fn):
                await self.run_fn(*args)
            else:
                # Note: a sync callable keeps running in its thread after a timeout/cancel
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, lambda: self.run_fn(*args))
        else:
            raise RuntimeError("Task has no cmd or run_fn")

    async def _run_cmd(self, pm: ProcessManager) -> None:
        expanded = [os.path.expandvars(arg) for arg in self.cmd]
        info = await pm.start(
            expanded,
            env=self.env,
            cwd=str(self.working_dir) if self.working_dir else None,
            pid=self._new_run_id(),
        )
        self.last_run_id = info.pid
        logger.info("Task '%s' started as process %s: %s", self.name, info.pid, expanded)
        try:
            done = await pm.wait(info.pid)
        except BaseException:
            # Cancelled (scheduler stop or timeout) — don't leave the process running
            await _stop_process(pm, info.pid)
            raise
        await self._prune_runs(pm)
        if done.exit_code != 0:
            raise RuntimeError(
                f"Command exited with code {done.exit_code} "
                f"(output: geenii pm output {info.pid} [--stream stderr])"
            )

    def _run_id_prefix(self) -> str:
        # Process IDs allow [A-Za-z0-9_-] only and must start with a letter or digit
        safe = re.sub(r"[^A-Za-z0-9_-]", "-", self.name)[:40] or "task"
        return safe if safe[0].isalnum() else f"t{safe[:39]}"

    def _new_run_id(self) -> str:
        return f"{self._run_id_prefix()}-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:4]}"

    async def _prune_runs(self, pm: ProcessManager) -> None:
        """Delete finished runs of this task beyond the newest RUNS_KEPT_PER_TASK."""
        pattern = re.compile(rf"^{re.escape(self._run_id_prefix())}-\d{{8}}T\d{{6}}-[0-9a-f]{{4}}$")
        runs = [p for p in await pm.list(include_finished=True)
                if pattern.match(p.pid) and p.state not in (ProcessState.PENDING, ProcessState.RUNNING)]
        for old in runs[RUNS_KEPT_PER_TASK:]:  # list() is sorted newest first
            try:
                await pm.cleanup(old.pid)
            except (KeyError, RuntimeError, OSError) as exc:
                logger.warning("Could not remove old run %s of task '%s': %s", old.pid, self.name, exc)


async def _stop_process(pm: ProcessManager, pid: str) -> None:
    """Kill a run (SIGTERM, then SIGKILL if it is still running after kill() returns)."""
    try:
        info = await pm.kill(pid)
        if info.state == ProcessState.RUNNING:
            await pm.kill(pid, force=True)
    except KeyError:
        pass  # finished in the meantime


class SchedulerConfig(pydantic.BaseModel):
    model_config = {"extra": "allow"}

    name: str
    interval: str
    cmd: list[str] | None = None
    module: str = ""
    params: list[str] | None = None
    env: dict[str, str] | None = None
    working_dir: str | None = None
    timeout: float | None = pydantic.Field(default=None, gt=0)
    allow_overlap: bool = False
    enabled: bool = True


def read_config(config_path: str | Path, existing_names: set[str] | frozenset[str] = frozenset()) -> list[ScheduledTask]:
    """Parse and load the enabled tasks in a scheduler config file.

    Invalid entries, disabled tasks and duplicate names (within the file or
    in existing_names) are logged and skipped.
    """
    config_path = Path(config_path)
    data = json.loads(config_path.read_text())

    raw_tasks: list[dict] = data.get("tasks", [])
    if not raw_tasks:
        logger.warning("No tasks found in %s", config_path)
        return []

    names = set(existing_names)
    tasks: list[ScheduledTask] = []
    for entry in raw_tasks:
        try:
            task_conf = SchedulerConfig.model_validate(entry)
        except pydantic.ValidationError as e:
            logger.error("Invalid task configuration in %s: %s — skipping entry: %s", config_path, str(e), entry)
            continue

        if not task_conf.enabled:
            logger.info("Task '%s' is disabled — skipping", task_conf.name)
            continue

        if task_conf.name in names:
            logger.error("Duplicate task name '%s' in %s — skipping", task_conf.name, config_path)
            continue

        task = ScheduledTask(
            name=task_conf.name, interval=task_conf.interval,
            cmd=task_conf.cmd, module=task_conf.module, params=task_conf.params,
            env=task_conf.env, enabled=task_conf.enabled,
            working_dir=Path(task_conf.working_dir) if task_conf.working_dir else None,
            timeout=task_conf.timeout, allow_overlap=task_conf.allow_overlap,
        )
        try:
            task.load()
        except Exception:
            logger.exception("Failed to load task '%s' — skipping", task_conf.name)
            continue

        logger.info(
            "Loaded task '%s' (interval=%s, cmd=%s, next=%s)",
            task.name, task.interval, task.cmd, task.next_run(),
        )
        names.add(task.name)
        tasks.append(task)
    return tasks


def _definition(task: ScheduledTask) -> tuple:
    """The configurable parts of a task, for change detection on reload."""
    return (task.interval, task.cmd, task.module, task.params, task.env,
            task.working_dir, task.timeout, task.allow_overlap)


class Scheduler:
    """Reads tasks from a config file and runs them on schedule."""

    def __init__(self, pm: ProcessManager | None = None) -> None:
        # Runs cmd tasks. The daemon passes its own; standalone schedulers use the default directory.
        self.pm = pm or ProcessManager()
        self.tasks: list[ScheduledTask] = []
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._lock: asyncio.Lock = asyncio.Lock()
        self._schedule: dict[str, datetime] = {}
        self._last_run: dict[str, datetime] = {}
        self._running_tasks: set[asyncio.Task] = set()
        self._active: dict[str, asyncio.Task] = {}  # latest run per task name, for overlap checks

    @property
    def status(self):
        return {
            "num_tasks": len(self.tasks),
            "running_tasks": len(self._running_tasks),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "running" if self._task and not self._task.done() else "stopped",
            "tasks": [
                {
                    "name": task.name,
                    "interval": task.interval,
                    "cmd": task.cmd,
                    "module": task.module or None,
                    "next_run": self._schedule.get(task.name).isoformat() if self._schedule.get(task.name) else None,
                    "last_run": self._last_run.get(task.name).isoformat() if self._last_run.get(task.name) else None,
                    "running": self._is_running(task.name),
                    "last_run_id": task.last_run_id,
                    "enabled": task.enabled,
                }
                for task in self.tasks
            ],
        }

    def _has_task(self, name: str) -> bool:
        return any(t.name == name for t in self.tasks)

    def _is_running(self, name: str) -> bool:
        t = self._active.get(name)
        return t is not None and not t.done()

    # -- configuration --------------------------------------------------------

    def load_config(self, config_path: str | Path) -> None:
        """Add the tasks from config_path. Problems are logged; invalid entries are skipped."""
        config_path = Path(config_path) if config_path else None
        if config_path is None:
            logger.error("No config path provided, cannot load tasks")
            return
        if not config_path.exists():
            logger.error("Config file %s does not exist, cannot load tasks", config_path)
            return
        self.tasks.extend(read_config(config_path, existing_names={t.name for t in self.tasks}))

    async def reload_config(self, config_path: str | Path) -> dict[str, list[str]]:
        """Replace the task list with the tasks in config_path, while the scheduler runs.

        Runs already in progress continue. New tasks and tasks whose interval
        changed are rescheduled; other changes take effect at the next run.
        Raises FileNotFoundError if the file does not exist.
        """
        config_path = Path(config_path)
        if not config_path.is_file():
            raise FileNotFoundError(f"Config file {config_path} does not exist")
        new_tasks = read_config(config_path)

        async with self._lock:
            old = {t.name: t for t in self.tasks}
            new = {t.name: t for t in new_tasks}
            now = datetime.now(timezone.utc)
            for name in set(old) - set(new):
                self._schedule.pop(name, None)
                self._last_run.pop(name, None)
            for task in new_tasks:
                prev = old.get(task.name)
                if prev is not None:
                    task.last_run_id = prev.last_run_id
                if prev is None or prev.interval != task.interval:
                    self._schedule[task.name] = task.next_run(after=now)
            self.tasks = new_tasks

        changes = {
            "added": sorted(set(new) - set(old)),
            "removed": sorted(set(old) - set(new)),
            "updated": sorted(n for n in set(old) & set(new) if _definition(old[n]) != _definition(new[n])),
        }
        logger.info("Reloaded scheduler config %s: %s", config_path, changes)
        return changes

    # -- lifecycle ------------------------------------------------------------

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            raise RuntimeError("Scheduler is already running")
        self._stop_event.clear()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._stop_event.is_set():
            logger.warning("Scheduler stop() called but it's already stopping")
            return
        logger.info("Scheduler stopping...")
        self._stop_event.set()
        if self._task:
            self._task.cancel()
        # Cancelling a cmd task terminates its subprocess (see ScheduledTask._run_cmd)
        for t in list(self._running_tasks):
            t.cancel()

    async def wait_until_stopped(self) -> None:
        if self._task:
            try:
                logger.info("Waiting for scheduler to stop...")
                await self._task
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.exception("Scheduler main task exited with error %s", e)
        if self._running_tasks:
            logger.info("Waiting for %d running task(s) to finish...", len(self._running_tasks))
            await asyncio.gather(*self._running_tasks, return_exceptions=True)
        logger.info("Scheduler stopped.")

    # -- tasks api ------------------------------------------------------------

    async def add_task(self, task: ScheduledTask) -> None:
        async with self._lock:
            if self._has_task(task.name):
                raise ValueError(f"Task '{task.name}' already exists")
            task.load()
            self.tasks.append(task)
            logger.info("Added task '%s' (interval=%s, next=%s)", task.name, task.interval, task.next_run())
            self._schedule[task.name] = task.next_run(after=datetime.now(timezone.utc))

    async def run_now(self, task_name: str) -> None:
        """Start a run of task_name immediately, outside its schedule (does not wait for it).

        Raises KeyError for unknown tasks and RuntimeError if the previous run is
        still in progress and the task does not allow overlap.
        """
        async with self._lock:
            task = next((t for t in self.tasks if t.name == task_name), None)
            if task is None:
                raise KeyError(f"Unknown task: {task_name}")
            if not task.allow_overlap and self._is_running(task.name):
                raise RuntimeError(f"Task '{task_name}' is already running")
            logger.info("Task '%s' started manually", task.name)
            self._launch(task)
            self._last_run[task.name] = datetime.now(timezone.utc)

    async def remove_task(self, task_name: str) -> None:
        async with self._lock:
            _task = next((t for t in self.tasks if t.name == task_name), None)
            if _task:
                self.tasks.remove(_task)
                logger.info("Removed task '%s'", task_name)
            self._schedule.pop(task_name, None)

    # -- main loop ------------------------------------------------------------

    def _launch(self, task: ScheduledTask) -> None:
        _t = asyncio.create_task(task.run(self.pm), name=f"task:{task.name}")
        self._running_tasks.add(_t)
        self._active[task.name] = _t

        def _done(t: asyncio.Task) -> None:
            self._running_tasks.discard(t)
            if self._active.get(task.name) is t:
                del self._active[task.name]
            if not t.cancelled() and t.exception():
                logger.error("Task raised an exception", exc_info=t.exception())

        _t.add_done_callback(_done)

    async def _run(self) -> None:
        logger.info("Scheduler started with %d task(s)", len(self.tasks))

        self._schedule.update({
            task.name: task.next_run(after=None) for task in self.tasks
        })

        while not self._stop_event.is_set():
            now = datetime.now(timezone.utc)
            async with self._lock:
                removals = []
                for task in self.tasks:
                    next_time = self._schedule.get(task.name)
                    if next_time is None:
                        next_time = task.next_run(after=now)
                        self._schedule[task.name] = next_time

                    if now >= next_time:
                        if not task.allow_overlap and self._is_running(task.name):
                            logger.warning("Task '%s' is due but its previous run is still in progress — skipping",
                                           task.name)
                        else:
                            logger.info("Task '%s' is due: now=%s, offset=%s", task.name, now, now - next_time)
                            self._launch(task)
                            self._last_run[task.name] = now

                        if task.is_oneshot:
                            logger.info("Task '%s' is oneshot (at:), marked for removal", task.name)
                            removals.append(task)
                        else:
                            self._schedule[task.name] = task.next_run(after=now)

                for task in removals:
                    self.tasks.remove(task)
                    self._schedule.pop(task.name, None)
                    self._last_run.pop(task.name, None)
                    logger.info("Removed oneshot task '%s'", task.name)

            await asyncio.sleep(1)


def main():
    """`geenii-scheduler <config>`: runs the geenii daemon with this scheduler config.

    The scheduler no longer runs as a separate service; the daemon hosts it
    together with the process manager and the supervisor.
    """
    from geenii.daemon.server import main as daemon_main

    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not config_path:
        logger.error("No config path provided, exiting")
        sys.exit(1)
    daemon_main(["--scheduler-config", config_path])


if __name__ == "__main__":
    main()
