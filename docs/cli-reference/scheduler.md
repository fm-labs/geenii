# geenii scheduler

Manage and run the task scheduler. Scheduled tasks run inside the
[geenii daemon](daemon.md).

## Synopsis

```
geenii scheduler <command> [--config PATH]
```

All subcommands accept `--config`/`-c` to specify the scheduler config JSON
file (defaults to `.geenii/scheduler.json`).

**Live and offline.** When a daemon is running with the **same** config file,
`status`, `run`, `add`, `remove` and `reload` work against it. When there is
no daemon, or it uses a different config, they work on the file alone and say
so. The daemon is found through `GEENII_SOCKET` (or `GEENII_PM_SOCKET`), and
otherwise through the default socket.

## Commands

### start

```
geenii scheduler start [--config PATH]
```

Alias for [`geenii daemon start --scheduler-config PATH`](daemon.md). It runs
the daemon, which schedules the tasks from the config and also hosts the
process manager and the supervisor. A missing config file produces a warning,
and the scheduler runs without tasks.

### status

```
geenii scheduler status [--config PATH]
```

Show the scheduled tasks in a table.

- **Live:** the daemon's actual state, with next run, last run, and whether a
  run is in progress (`running` or `idle`).
- **Offline:** the tasks from the file with their computed next run times.

### list

```
geenii scheduler list [--config PATH]
```

List all configured tasks from the config file, showing name, interval,
command, and enabled/disabled state.

### add

```
geenii scheduler add <NAME> <CMD>... --interval <SPEC> [OPTIONS]
```

Add a task to the scheduler config. A running daemon that uses this config
reloads it right away.

#### Arguments

| Argument | Description |
|---|---|
| `NAME` | Task identifier |
| `CMD` | Command to run (remaining arguments) |

#### Options

| Option | Short | Description |
|---|---|---|
| `--interval` | `-i` | Schedule: `cron:EXPRESSION` or `at:DATETIME` (required) |
| `--env` | `-e` | Environment variable in `KEY=VALUE` format (repeatable) |
| `--disabled` | | Add the task in disabled state |
| `--timeout` | `-t` | Kill the task if it runs longer than this many seconds |
| `--allow-overlap` | | Start a new run even if the previous run is still in progress |
| `--config` | | Path to scheduler config JSON file |

### remove

```
geenii scheduler remove <NAME> [--config PATH]
```

Remove a task from the scheduler config. A running daemon that uses this
config reloads it right away; a run already in progress is allowed to finish.

### reload

```
geenii scheduler reload [--config PATH]
```

Make the running daemon re-read its config, for example after editing the
file by hand. It prints which tasks were added, removed or updated.

- New tasks, and tasks whose interval changed, are rescheduled.
- Other changes (command, env, timeout, ...) take effect at the next run.
- Runs in progress continue.

Exits with code 1 if no daemon is running with this config.

### run

```
geenii scheduler run <NAME> [--config PATH] [--local]
```

Run a single task immediately, bypassing its schedule.

- **Live:** the run starts inside the daemon and the command returns right
  away. The output goes to the daemon's log, and `status` shows the task as
  `running` until it finishes. It fails if the previous run is still going
  and the task doesn't allow overlap.
- **Offline, or with `--local`:** the task runs in this process, and the
  command waits for it to finish.

## Examples

```bash
geenii scheduler add cleanup echo cleanup --interval 'cron:0 * * * *'
geenii scheduler add oneshot echo done --interval 'at:2026-07-21T18:00:00Z'
geenii scheduler add backup ./backup.sh --interval 'cron:0 3 * * *' --timeout 1800
geenii scheduler run cleanup
geenii scheduler list
geenii scheduler status
geenii scheduler reload
geenii scheduler start
```

## Related Entry Points

- `geenii-scheduler <config.json>` is an alias for
  `geenii-daemon --scheduler-config <config.json>`.
