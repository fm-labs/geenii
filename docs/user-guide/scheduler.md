# Scheduler

`geenii/scheduler.py` is a standalone cron-style task runner, typically used to
run agents on a schedule (reminders, monitors, periodic summaries).

## Running

The scheduler can be started via the CLI or as a standalone entry point:

```bash
# via CLI
geenii scheduler start --config /path/to/scheduler.json

# standalone entry point
geenii-scheduler /path/to/.geenii/scheduler.json
```

The process loads the config, starts an asyncio loop that checks due tasks
every second, and runs until SIGINT/SIGTERM (graceful shutdown waits for
running tasks).

See [cli.md](cli.md) for the full set of `geenii scheduler` subcommands
(`start`, `status`, `list`, `add`, `remove`, `run`).

## Task configuration

```json
{
  "tasks": [
    {
      "enabled": true,
      "name": "drink_more_water_reminder",
      "interval": "cron:* * * * *",
      "cmd": ["$GEENII_BIN", "agent", "--name", "mac-bot",
              "Display a friendly desktop notification reminding me to drink water."],
      "env": {"SOME_VAR": "value"}
    },
    {
      "name": "one_time_job",
      "interval": "at:2026-07-08T18:00:00+00:00",
      "module": "geenii.core.tasks.cleanup"
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `name` | Unique task name (required) |
| `interval` | Schedule expression (required) — see [Interval formats](#interval-formats) |
| `cmd` | Command to run as a subprocess (list of strings). Environment variable placeholders (`$VAR`) are expanded from the scheduler process environment |
| `module` | Dot-path to a Python callable (e.g. `geenii.core.tasks.run_proc`). The last segment is the function name. Mutually exclusive with `cmd` |
| `env` | Extra environment variables merged into the subprocess environment (only applies to `cmd` tasks) |
| `enabled` | When `false`, the task is skipped during config loading (default: `true`) |

A task must have either `cmd` or `module` set. Invalid entries (bad interval,
unresolvable module) are logged and skipped; the scheduler keeps running with
the remaining tasks.

### Interval formats

The `interval` field uses a prefixed format:

| Prefix | Meaning | Example |
|---|---|---|
| `cron:` | Recurring cron schedule (5-field, evaluated in UTC via croniter) | `cron:*/5 * * * *` |
| `at:` | One-shot execution at an ISO datetime (task is removed after it runs) | `at:2026-07-21T18:00:00Z` |

## Task execution

### `cmd` tasks (subprocess)

The `cmd` list is executed as a subprocess. Each element is expanded with
`os.path.expandvars`, and `env` values are merged into the process environment.
stdout/stderr are captured and logged.

```json
{
  "name": "agent_reminder",
  "interval": "cron:0 9 * * *",
  "cmd": ["geenii", "agent", "-n", "mac-bot", "Good morning!"]
}
```

### `module` tasks (Python callable)

The `module` string is resolved to a Python callable: `geenii.core.tasks.run_proc`
imports `geenii.core.tasks` and calls `run_proc()`. Both sync (run in the
executor) and async functions are supported. The function is called with no
arguments.

## Built-in task functions

Built-in task functions live in `geenii/core/tasks.py`:

| Function | Behavior |
|---|---|
| `run_proc` | Runs a subprocess: the first argument is shlex-split and remaining args appended; `env` is merged into the process environment. Called with `(params: list[str], env: dict)` |
| `cleanup` | Maintenance stub (logs only) |
| `run_agent` | Stub for in-process agent runs (logs only) |

These are intended for use with `module`-style tasks, but note that the
scheduler currently calls module functions with no arguments. To run
subprocesses, prefer `cmd` tasks instead.

## Runtime behavior

- Next-run times are precalculated per task; due tasks are spawned as asyncio
  tasks, so a slow task does not block the loop or other tasks.
- Task failures are caught and logged; the schedule continues.
- One-shot tasks (`at:` interval) are automatically removed after execution.
- Tasks can be added/removed at runtime via `Scheduler.add_task()` /
  `remove_task()` when embedding the scheduler in another process.
- The `Scheduler.status` property returns a dict with task states, next/last
  run times, and overall scheduler status.

## Process supervisor

`geenii/supervisor.py` is a related but separate building block: a
desired-state asyncio process supervisor (start/stop/restart with exponential
backoff, per-process ring-buffer log bus with live subscription). It is a
library used by the server repository and has no CLI in this repo.
