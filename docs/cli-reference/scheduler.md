# geenii scheduler

Manage and run the task scheduler.

## Synopsis

```
geenii scheduler <command> [--config PATH]
```

All subcommands accept `--config`/`-c` to specify the scheduler config JSON
file (defaults to `.geenii/scheduler.json`).

## Commands

### start

```
geenii scheduler start [--config PATH]
```

Start the scheduler and run tasks on their configured schedules.

### status

```
geenii scheduler status [--config PATH]
```

Show loaded tasks and their next run times in a rich table.

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

Add a task to the scheduler config.

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
| `--config` | | Path to scheduler config JSON file |

### remove

```
geenii scheduler remove <NAME> [--config PATH]
```

Remove a task from the scheduler config.

### run

```
geenii scheduler run <NAME> [--config PATH]
```

Run a single task immediately, bypassing its schedule.

## Examples

```bash
geenii scheduler add cleanup echo cleanup --interval 'cron:0 * * * *'
geenii scheduler add oneshot echo done --interval 'at:2026-07-21T18:00:00Z'
geenii scheduler run cleanup
geenii scheduler list
geenii scheduler status
geenii scheduler start
```

## Related Entry Points

- `geenii-scheduler <config.json>` — runs the scheduler as a standalone
  process without the rest of the CLI.
