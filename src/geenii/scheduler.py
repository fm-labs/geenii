"""
Simple cron-style task scheduler.

Reads task definitions from a JSON config file. Each task specifies a cron
expression and a dot-separated Python module path to a function to execute.

The scheduler runs in an asyncio event loop, calculates the next execution time for each task,
and executes them at the scheduled times.

Tasks can be added or removed at runtime. Thread-safe execution and error handling ensure the scheduler remains stable even if tasks fail.

Config file format (tasks.json):
    {
        "tasks": [
            {
                "name": "cleanup",
                "cron": "0 * * * *",
                "module": "geenii.tasks.cleanup"
            }
        ]
    }

Usage:
    python scheduler.py                  # uses tasks.json
    python scheduler.py my_tasks.json    # uses custom config path
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import pydantic
from croniter import croniter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("scheduler")


@dataclass
class ScheduledTask:
    """A single scheduled task."""

    name: str
    at: datetime | None = None  # optional fixed execution time, overrides cron if set
    cron: str | None = None  # cron expression like "0 * * * *" for hourly execution
    module: str = ""  # dot-separated module path to the function to run, e.g. "myapp.tasks.cleanup"
    run_fn: Callable[[], Any] | None = field(default=None, repr=False)
    args: list[str] | None = None
    oneshot: bool = False  # if true, the task will be removed after running once
    env: dict[str, str] | None = None


    def load(self) -> None:
        """Import the module and resolve the function. The last part of the module path is the function name."""
        if self.at and self.cron:
            raise ValueError("Task schedule cannot have both 'at' and 'cron' defined")
        elif not self.at and not self.cron:
            raise ValueError(f"Task '{self.name}' must have either 'at' or 'cron' defined")
        elif self.at and self.oneshot is False:
            logger.warning("Task scheduled with 'at' will be treated as oneshot")
            self.oneshot = True

        if self.run_fn is None:
            if self.module:
                parts = self.module.split(".")
                if len(parts) < 2:
                    raise ValueError(f"Module path '{self.module}' must include at least one dot to separate module and function")
                module_name = ".".join(parts[:-1])
                fn_name = parts[-1]

                mod = importlib.import_module(module_name)
                fn = getattr(mod, fn_name, None)
                if fn is None or not callable(fn):
                    raise AttributeError(
                        f"Module '{self.module}' does not export a callable '{fn_name}' function"
                    )
                self.run_fn = fn
            else:
                raise ValueError("No module specified for task and run_fn is not set")

    def next_run(self, after: datetime | None = None) -> datetime:
        """Return the next execution time as a UTC datetime."""
        if self.at is not None:
            return self.at.astimezone(timezone.utc)

        if self.cron is not None:
            base = after or datetime.now(timezone.utc)
            return croniter(self.cron, base).get_next(datetime).replace(tzinfo=timezone.utc)

        raise ValueError(f"Task '{self.name}' has no valid schedule (missing 'at' or 'cron')")

    async def run(self) -> None:
        """Run the task function, catching exceptions."""
        if self.run_fn is None:
            raise RuntimeError("Task function not loaded")
        logger.info("Running task '%s'", self.name)
        try:
            fn_args = self.args or []
            fn_env = self.env or {}
            if inspect.iscoroutinefunction(self.run_fn):
                await self.run_fn(fn_args, fn_env)  # type: ignore
            else:
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self.run_fn, fn_args, fn_env)  # type: ignore
            logger.info("Task '%s' completed successfully", self.name)
        except Exception:
            logger.exception("Task '%s' failed", self.name)


class SchedulerConfig(pydantic.BaseModel):
    model_config = {
        "extra": "allow"
    }

    name: str
    at: datetime | None = None
    cron: str | None = None
    module: str = ""
    cmd: list[str] | None = None
    args: list[str] | None = None
    env: dict[str, str] | None = None
    enabled: bool = False
    oneshot: bool = False

    @property
    def args_parsed(self) -> list[str]:
        """Replace all environment variable placeholders in args with their values from env."""
        if not self.args:
            return []
        #env = self.env or {}
        parsed_args = []
        for arg in self.args:
            #for key, value in env.items():
            #    placeholder = f"${{{key}}}"
            #    arg = arg.replace(placeholder, value)
            arg = os.path.expandvars(arg)
            parsed_args.append(arg)
        return parsed_args


class Scheduler:
    """Reads tasks from a config file and runs them on their cron schedule."""

    def __init__(self) -> None:
        self.tasks: list[ScheduledTask] = []
        self._stop_event = asyncio.Event() # event to signal the scheduler loop to stop
        self._task: asyncio.Task | None = None # asyncio task for the scheduler loop
        self._lock: asyncio.Lock = asyncio.Lock() # lock to protect access to tasks list
        self._schedule: dict[str, datetime] = {} # pre-calculated next run times for tasks
        self._last_run: dict[str, datetime] = {} # track last run times for tasks
        self._running_tasks: set[asyncio.Task] = set() # track currently running tasks

    @property
    def status(self):
        """Return a summary of the scheduler status."""
        return {
            "num_tasks": len(self.tasks),
            "running_tasks": len(self._running_tasks),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "running" if self._task and not self._task.done() else "stopped",
            "tasks": [
                {
                    "name": task.name,
                    "module": task.module,
                    "args": task.args,
                    "next_run": self._schedule.get(task.name).isoformat() if self._schedule.get(task.name) else None,
                    "last_run": self._last_run.get(task.name).isoformat() if self._last_run.get(task.name) else None,
                    "oneshot": task.oneshot,
                    #"enabled": task.enabled,
                }
                for task in self.tasks
            ],
        }

    # -- configuration --------------------------------------------------------

    def load_config(self, config_path: str | Path) -> None:
        """Parse the JSON config and import each task module."""
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

            if task_conf.cron and not croniter.is_valid(task_conf.cron):
                logger.error("Invalid cron expression '%s' for task '%s' — skipping", task_conf.cron, task_conf.name)
                continue

            #if at_expr:
            #    at_expr = datetime.fromisoformat(at_expr).astimezone(timezone.utc)

            task = ScheduledTask(name=task_conf.name, at=task_conf.at, cron=task_conf.cron,
                                 module=task_conf.module, args=task_conf.args_parsed, env=task_conf.env, )
            try:
                task.load()
            except Exception:
                logger.exception("Failed to load module '%s' for task '%s' — skipping",
                                 task_conf.module, task_conf.name)
                continue

            logger.info(
                "Loaded task '%s' (module=%s, cron=%s, next=%s)",
                task.name,
                task.module,
                task.cron,
                task.next_run(),
            )
            self.tasks.append(task)

    # -- lifecycle ------------------------------------------------------------

    async def start(self) -> None:
        if self._task is not None:
            raise RuntimeError("Scheduler is already running")
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        """Signal the scheduler loop to exit."""
        if self._stop_event.is_set():
            logger.warning("Scheduler stop() called but it's already stopping")
            return

        logger.info("Scheduler stopping…")
        self._stop_event.set()
        if self._task:
            self._task.cancel()
        for t in list(self._running_tasks):
            t.cancel()

    async def wait_until_stopped(self) -> None:
        """Wait for the scheduler loop to finish after stop() is called."""
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
        """Add a new task to the scheduler at runtime."""
        async with self._lock:
            task.load()
            self.tasks.append(task)
            logger.info(
                "Added task '%s' (module=%s, at=%s, cron=%s, next=%s)",
                task.name,
                task.module,
                task.at,
                task.cron,
                task.next_run(),
            )
            self._schedule[task.name] = task.next_run(after=datetime.now(timezone.utc))

    async def remove_task(self, task_name: str) -> None:
        """Remove a task by name."""
        async with self._lock:
            _task = next((t for t in self.tasks if t.name == task_name), None)
            if _task:
                self.tasks.remove(_task)
                logger.info("Removed task '%s'", task_name)
            if task_name in self._schedule:
                self._schedule.pop(task_name, None)
                logger.info("Removed schedule for '%s'", task_name)


    # -- main loop ------------------------------------------------------------

    async def _run(self) -> None:
        """Block and run the scheduling loop until stopped."""
        logger.info("Scheduler started with %d task(s)", len(self.tasks))

        # Pre-calculate next run times.
        self._schedule.update({
            task.name: task.next_run() for task in self.tasks
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
                        logger.info("Added schedule for task '%s', next run at %s", task.name, next_time)

                    #logger.info("Checking task '%s': now=%s, next_run=%s", task.name, now, next_time)
                    if now >= next_time:
                        logger.info("Task '%s' is due: now=%s, offset=%s", task.name, now, now - next_time)
                        _run = asyncio.create_task(task.run())
                        self._running_tasks.add(_run)
                        _run.add_done_callback(lambda t: self._running_tasks.discard(t))

                        if task.oneshot:
                            logger.info("Task '%s' is oneshot, marked for removal", task.name)
                            removals.append(task)
                        else:
                            self._last_run[task.name] = now
                            self._schedule[task.name] = task.next_run(after=now)

                for task in removals:
                    self.tasks.remove(task)
                    self._schedule.pop(task.name, None)
                    self._last_run.pop(task.name, None)
                    logger.info("Removed task '%s'", task.name)

            # Sleep in short intervals so we can react to stop quickly.
            await asyncio.sleep(1)


# if __name__ == "__main__":
#     async def hello():
#         print("Hello from the scheduled task!")
#         return "Hello result"
#
#
#     def hello_sync():
#         print("Hello from the scheduled task (sync)!")
#         return "Hello sync result"
#
#
#     async def run_scheduler(config_path: str = DEFAULT_CONFIG_PATH) -> None:
#         scheduler = Scheduler()
#         scheduler.load_config(config_path)
#
#         # async def shutdown_handler():
#         #     await scheduler.stop()
#         #     await scheduler.wait_until_stopped()
#         #     logger.info("Scheduler shutdown complete.")
#         #
#         # loop = asyncio.get_running_loop()
#         # for sig in (signal.SIGINT, signal.SIGTERM):
#         #     loop.add_signal_handler(sig, lambda: asyncio.create_task(shutdown_handler()))
#
#         await scheduler.start()
#         logger.info("Scheduler started.")
#
#         # dynamically add a cron tasks
#         await scheduler.add_task(ScheduledTask(
#             name="hello_task",
#             cron="* * * * *",  # every 15 seconds
#             # module="geenii.tasks.demo_tasks.hello",
#             module="",
#             run_fn=hello,
#         ))
#         await scheduler.add_task(ScheduledTask(
#             name="hello_sync_task",
#             cron="* * * * *",  # every minute
#             module="",
#             run_fn=hello_sync
#         ))
#         await scheduler.add_task(ScheduledTask(
#             name="hello_sync_task2",
#             at=datetime.now(timezone.utc) + timedelta(seconds=30),  # run once 30 seconds from now
#             module="",
#             run_fn=hello_sync,
#             oneshot=True,
#         ))
#
#         # sleep for a short while
#         await asyncio.sleep(90)
#
#         await scheduler.stop()
#         logger.info("Scheduler stopping.")
#         await scheduler.wait_until_stopped()
#         logger.info("Scheduler stopped.")
#
#
#     config_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_CONFIG_PATH
#     asyncio.run(run_scheduler(config_path))
