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
                "env": {"CLEANUP_DRY_RUN": "true"}
            }
        ]
    }

Interval formats:
    "cron:EXPRESSION"   – recurring cron schedule, e.g. "cron:*/5 * * * *"
    "at:DATETIME"       – one-shot execution at an ISO datetime, e.g. "at:2026-07-21T18:00:00Z"
"""
from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import logging
import os
import signal
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pydantic
from croniter import croniter

logger = logging.getLogger(__name__)


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


@dataclass
class ScheduledTask:
    """A single scheduled task."""

    name: str
    interval: str
    cmd: list[str] | None = None
    module: str = ""
    run_fn: Callable[[], Any] | None = field(default=None, repr=False)
    enabled: bool = True
    env: dict[str, str] | None = None
    working_dir: Path | None = None

    def load(self) -> None:
        """Validate interval and resolve execution target (cmd or module)."""
        parse_interval(self.interval)

        if self.cmd:
            return
        if self.run_fn is not None:
            return
        if self.module:
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
        else:
            raise ValueError("Task must have 'cmd', 'module', or 'run_fn' set")

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

    async def run(self) -> None:
        """Run the task as a subprocess (cmd) or Python callable (run_fn)."""
        logger.info("Running task '%s'", self.name)
        try:
            if self.cmd:
                await self._run_cmd()
            elif self.run_fn is not None:
                if inspect.iscoroutinefunction(self.run_fn):
                    await self.run_fn()
                else:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, self.run_fn)
            else:
                raise RuntimeError("Task has no cmd or run_fn")
            logger.info("Task '%s' completed successfully", self.name)
        except Exception:
            logger.exception("Task '%s' failed", self.name)

    async def _run_cmd(self) -> None:
        expanded = [os.path.expandvars(arg) for arg in self.cmd]
        merged_env = {**os.environ, **(self.env or {})}
        logger.info("Task '%s' executing: %s", self.name, expanded)
        proc = await asyncio.create_subprocess_exec(
            *expanded,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=merged_env,
            cwd=str(self.working_dir) if self.working_dir else None,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            logger.info("Task '%s' stdout: %s", self.name, stdout.decode(errors="replace").rstrip())
        if stderr:
            logger.warning("Task '%s' stderr: %s", self.name, stderr.decode(errors="replace").rstrip())
        if proc.returncode != 0:
            raise RuntimeError(f"Command exited with code {proc.returncode}")


class SchedulerConfig(pydantic.BaseModel):
    model_config = {"extra": "allow"}

    name: str
    interval: str
    cmd: list[str] | None = None
    module: str = ""
    env: dict[str, str] | None = None
    enabled: bool = True


class Scheduler:
    """Reads tasks from a config file and runs them on schedule."""

    def __init__(self) -> None:
        self.tasks: list[ScheduledTask] = []
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task | None = None
        self._lock: asyncio.Lock = asyncio.Lock()
        self._schedule: dict[str, datetime] = {}
        self._last_run: dict[str, datetime] = {}
        self._running_tasks: set[asyncio.Task] = set()

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
                    "next_run": self._schedule.get(task.name).isoformat() if self._schedule.get(task.name) else None,
                    "last_run": self._last_run.get(task.name).isoformat() if self._last_run.get(task.name) else None,
                    "enabled": task.enabled,
                }
                for task in self.tasks
            ],
        }

    # -- configuration --------------------------------------------------------

    def load_config(self, config_path: str | Path) -> None:
        config_path = Path(config_path) if config_path else None
        if config_path is None:
            logger.error("No config path provided, cannot load tasks")
            return
        if not config_path.exists():
            logger.error("Config file %s does not exist, cannot load tasks", config_path)
            return

        text = config_path.read_text()
        data = json.loads(text)

        raw_tasks: list[dict] = data.get("tasks", [])
        if not raw_tasks:
            logger.warning("No tasks found in %s", config_path)
            return

        for entry in raw_tasks:
            try:
                task_conf = SchedulerConfig.model_validate(entry)
            except pydantic.ValidationError as e:
                logger.error("Invalid task configuration in %s: %s — skipping entry: %s", config_path, str(e), entry)
                continue

            if not task_conf.enabled:
                logger.info("Task '%s' is disabled — skipping", task_conf.name)
                continue

            task = ScheduledTask(
                name=task_conf.name, interval=task_conf.interval,
                cmd=task_conf.cmd, module=task_conf.module,
                env=task_conf.env, enabled=task_conf.enabled,
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
            self.tasks.append(task)

    # -- lifecycle ------------------------------------------------------------

    async def start(self) -> None:
        if self._task is not None:
            raise RuntimeError("Scheduler is already running")
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._stop_event.is_set():
            logger.warning("Scheduler stop() called but it's already stopping")
            return
        logger.info("Scheduler stopping...")
        self._stop_event.set()
        if self._task:
            self._task.cancel()
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
            task.load()
            self.tasks.append(task)
            logger.info("Added task '%s' (interval=%s, next=%s)", task.name, task.interval, task.next_run())
            self._schedule[task.name] = task.next_run(after=datetime.now(timezone.utc))

    async def remove_task(self, task_name: str) -> None:
        async with self._lock:
            _task = next((t for t in self.tasks if t.name == task_name), None)
            if _task:
                self.tasks.remove(_task)
                logger.info("Removed task '%s'", task_name)
            self._schedule.pop(task_name, None)

    # -- main loop ------------------------------------------------------------

    async def _run(self) -> None:
        logger.info("Scheduler started with %d task(s)", len(self.tasks))

        self._schedule.update({
            task.name: task.next_run(after=None) for task in self.tasks
        })

        def _handle_task_result(t: asyncio.Task) -> None:
            self._running_tasks.discard(t)
            if not t.cancelled() and t.exception():
                logger.error("Task raised an exception", exc_info=t.exception())

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
                        logger.info("Task '%s' is due: now=%s, offset=%s", task.name, now, now - next_time)
                        _t = asyncio.create_task(task.run())
                        self._running_tasks.add(_t)
                        _t.add_done_callback(_handle_task_result)

                        if task.is_oneshot:
                            logger.info("Task '%s' is oneshot (at:), marked for removal", task.name)
                            removals.append(task)
                        else:
                            self._last_run[task.name] = now
                            self._schedule[task.name] = task.next_run(after=now)

                for task in removals:
                    self.tasks.remove(task)
                    self._schedule.pop(task.name, None)
                    self._last_run.pop(task.name, None)
                    logger.info("Removed oneshot task '%s'", task.name)

            await asyncio.sleep(1)


def main():
    from geenii.logs import init_logging
    init_logging()

    async def shutdown_handler():
        logger.info("Shutting down...")
        await scheduler.stop()
        await scheduler.wait_until_stopped()
        logger.info("Scheduler shutdown complete.")

    async def run_scheduler(scheduler: Scheduler) -> None:
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown_handler()))

        await scheduler.start()
        logger.info("Scheduler started.")
        await scheduler.wait_until_stopped()
        logger.info("Scheduler stopped.")

    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    if not config_path:
        logger.error("No config path provided, exiting")
        sys.exit(1)
    scheduler = Scheduler()
    scheduler.load_config(config_path)
    asyncio.run(run_scheduler(scheduler))


if __name__ == "__main__":
    main()
