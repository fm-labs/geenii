# Scheduler

`geenii/scheduler.py` is a standalone cron-style task runner, typically used to
run agents on a schedule (reminders, monitors, periodic summaries).

## Running

```bash
geenii-scheduler /path/to/.geenii/scheduler.json
```

The process loads the config, starts an asyncio loop that checks due tasks
every second, and runs until SIGINT/SIGTERM (graceful shutdown waits for
running tasks). The `geenii scheduler start|stop|status` CLI subcommands are
placeholders and do not control this process yet.

## Task configuration

```json
{
  "tasks": [
    {
      "name": "drink_more_water_reminder",
      "cron": "* * * * *",
      "module": "geenii.core.tasks.run_proc",
      "args": ["$GEENII_BIN", "agent", "--name", "mac-bot",
               "Display a friendly desktop notification reminding me to drink water."],
      "env": {"SOME_VAR": "value"}
    },
    {
      "name": "one_time_job",
      "at": "2026-07-08T18:00:00+00:00",
      "module": "geenii.core.tasks.cleanup",
      "oneshot": true
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `name` | Unique task name |
| `cron` | Standard 5-field cron expression (evaluated in UTC, via croniter) |
| `at` | ISO datetime for a single fixed execution (mutually exclusive with `cron`; implies `oneshot`) |
| `module` | Dot-path to the function to run; the last segment is the function name (e.g. `geenii.core.tasks.run_proc`) |
| `args` | Arguments passed to the function. Environment variable placeholders (`$VAR`) are expanded from the scheduler process environment |
| `env` | Extra environment variables passed to the function |
| `oneshot` | Remove the task after its first run |
| `enabled` | Accepted in the config but **not currently enforced** — all valid tasks are loaded |

Invalid entries (bad cron expression, unresolvable module) are logged and
skipped; the scheduler keeps running with the remaining tasks.

Note: some example configs use a `cmd` key — the scheduler reads `args`, not
`cmd`, and a `module` must resolve to a callable (there is no implicit default
when loading from config).

## Task functions

The `module` function is called as `fn(args: list[str], env: dict)`; both sync
(run in the executor) and async functions are supported. Built-in task
functions live in `geenii/core/tasks.py`:

| Function | Behavior |
|---|---|
| `run_proc` | Runs a subprocess: `args[0]` is shlex-split and the remaining args appended; `env` is merged into the process environment. The standard way to schedule agent runs (`["geenii", "agent", "-n", "...", "<prompt>"]`) |
| `cleanup` | Maintenance stub (logs only) |
| `run_agent` | Stub for in-process agent runs (logs only) |

## Runtime behavior

- Next-run times are precalculated per task; due tasks are spawned as asyncio
  tasks, so a slow task does not block the loop or other tasks.
- Task failures are caught and logged (`$GEENII_CACHE_DIR/logs/scheduler.log`);
  the schedule continues.
- Tasks can be added/removed at runtime via `Scheduler.add_task()` /
  `remove_task()` when embedding the scheduler in another process.

## Process supervisor

`geenii/supervisor.py` is a related but separate building block: a
desired-state asyncio process supervisor (start/stop/restart with exponential
backoff, per-process ring-buffer log bus with live subscription). It is a
library used by the server repository and has no CLI in this repo.
