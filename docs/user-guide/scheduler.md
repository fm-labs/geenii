# Scheduler

`geenii/scheduler.py` is a cron-style task runner, typically used to run agents
on a schedule (reminders, monitors, periodic summaries). It runs inside the
[geenii daemon](../cli-reference/daemon.md), alongside the process manager and
the supervisor.

## Running

Start the daemon. By default it loads `.geenii/scheduler.json`:

```bash
geenii daemon start                                   # uses $GEENII_WORKING_DIR/.geenii/scheduler.json
geenii daemon start --scheduler-config /path/to/scheduler.json

# older forms, now aliases for the above
geenii scheduler start --config /path/to/scheduler.json
geenii-scheduler /path/to/.geenii/scheduler.json
```

The daemon loads the config and checks for due tasks every second. It runs
until `geenii daemon stop` or SIGINT/SIGTERM; a graceful shutdown stops
running tasks, including their child processes.

While the daemon runs, the `geenii scheduler` commands work against it:

- `status` shows the live state: next and last run, and whether a task is
  running.
- `run NAME` starts a run inside the daemon.
- `add` and `remove` update the running daemon right away.
- After editing `scheduler.json` by hand, run `geenii scheduler reload`.

Without a daemon, these commands work on the config file alone.

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
      "env": {"SOME_VAR": "value"},
      "timeout": 300
    },
    {
      "name": "one_time_job",
      "interval": "at:2026-07-08T18:00:00+00:00",
      "module": "geenii.core.tasks.run_agent",
      "params": ["mac-bot"]
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `name` | Task name (required). Must be unique; later entries with the same name are skipped |
| `interval` | Schedule expression (required). See [Interval formats](#interval-formats) |
| `cmd` | Command to run as a subprocess, as a list of strings. `$VAR` placeholders are filled in from the scheduler's environment |
| `module` | Dot-path to a Python callable (for example `geenii.core.tasks.cleanup`). The last segment is the function name. Use either `cmd` or `module`, not both |
| `params` | List of strings passed to a `module` callable (see [`module` tasks](#module-tasks-python-callable)) |
| `env` | Extra environment variables. For `cmd` tasks they are merged into the subprocess environment; `module` callables receive them as an argument |
| `working_dir` | Working directory for `cmd` tasks |
| `timeout` | Maximum run time in seconds. When exceeded, the run is cancelled and the command, including its child processes, is killed. Default: no limit |
| `allow_overlap` | When `true`, a new run starts even if the previous run of the same task is still going. Default: `false`, which means that run is skipped with a warning |
| `enabled` | When `false`, the task is skipped during config loading (default: `true`) |

A task must have either `cmd` or `module` set. Invalid entries are logged and
skipped, and the scheduler keeps running with the remaining tasks. Examples of
invalid entries: a bad interval, a module that can't be found, or a duplicate
name.

### Interval formats

The `interval` field uses a prefixed format:

| Prefix | Meaning | Example |
|---|---|---|
| `cron:` | Recurring cron schedule (5-field, evaluated in UTC via croniter) | `cron:*/5 * * * *` |
| `at:` | One-shot execution at an ISO datetime (task is removed after it runs) | `at:2026-07-21T18:00:00Z` |

## Task execution

### `cmd` tasks (subprocess)

The `cmd` list is executed as a process of the process manager, without a
shell. Each element is expanded with `os.path.expandvars`, and `env` values are
merged into the process environment. A non-zero exit code counts as a failure.

Every run gets its own **run ID**, such as `backup-20260925T030000-1a2b`,
which `geenii scheduler status` shows. The run's output is saved to disk, not
to the scheduler log:

```bash
geenii scheduler status                  # "Last Run ID" column
geenii pm output backup-20260925T030000-1a2b
geenii pm output backup-20260925T030000-1a2b --stream stderr
geenii pm list -a                        # all runs, with state and exit code
```

The newest 10 finished runs of each task are kept; older runs are deleted
automatically.

The command runs in its own process group. When the scheduler stops, or the
task's `timeout` is exceeded, the whole group receives `SIGTERM`, followed by
`SIGKILL` after 5 seconds. Child processes started by the command are
therefore stopped as well.

```json
{
  "name": "agent_reminder",
  "interval": "cron:0 9 * * *",
  "cmd": ["geenii", "agent", "-n", "mac-bot", "Good morning!"]
}
```

### `module` tasks (Python callable)

The `module` string is resolved to a Python callable: `geenii.core.tasks.cleanup`
imports `geenii.core.tasks` and looks up `cleanup`. Both sync functions (run in
a thread pool) and async functions are supported.

The call depends on the function's signature:

- If it accepts two arguments, it is called as `fn(params, env)`. `params`
  defaults to `[]` and `env` to `None`.
- If it takes no arguments, it is called as `fn()`.
- Any other signature is rejected when the config is loaded.

`timeout` cancels async functions. A sync function can't be interrupted: when
the timeout is exceeded, the scheduler stops waiting for it and logs the
timeout, but the function keeps running in its thread.

## Built-in task functions

Built-in task functions live in `geenii/core/tasks.py`:

| Function | Behavior |
|---|---|
| `cleanup` | Maintenance stub (logs only) |
| `run_agent` | Stub for in-process agent runs (logs only) |

To run a command, use a `cmd` task. It is killed when the task times out or
the scheduler stops, and its output is logged line by line.

## Runtime behavior

- Next-run times are calculated in advance for each task. Due tasks run as
  separate asyncio tasks, so a slow task does not block the loop or other
  tasks.
- Task failures and timeouts are caught and logged, and the schedule
  continues.
- A cron task whose previous run is still going is skipped for that slot,
  unless `allow_overlap` is set.
- Missed slots are not made up. If the scheduler was paused (for example
  while the host slept), each overdue task runs once and its next run is
  calculated from the current time.
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
