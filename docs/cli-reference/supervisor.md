# geenii supervisor

Keep long-running processes up. The supervisor runs inside the
[geenii daemon](daemon.md), so start that first (`geenii daemon start`). It
restarts a process when it exits, waiting longer after each crash in a row
(0.5s, 1s, 2s, … up to 30s).

There are two kinds of supervised processes:

| Kind | Created with | Lifetime | `status` shows |
|---|---|---|---|
| **File service** | `add`, or an entry in `services.json` | Started whenever the daemon starts | `file` |
| **Ad hoc** | `start` | Until it is stopped or the daemon stops | `ad hoc` |

`geenii daemon stop` stops both kinds. When the daemon starts again, only the
file services come back.

## services.json

By default the file is `$GEENII_DIR/services.json`; `geenii daemon start
--services-config PATH` chooses another one. `$VAR` in `cmd` and `cwd` is
filled in from the daemon's environment, and `~` in `cwd` is expanded.

```json
{
  "services": [
    {
      "name": "web",
      "cmd": ["python", "-m", "http.server", "8000"],
      "restart": true,
      "env": {"PYTHONUNBUFFERED": "1"},
      "cwd": "~/site",
      "enabled": true
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `name` | Unique service name (required) |
| `cmd` | Command as a list of strings (required); run without a shell |
| `restart` | Restart when it exits (default `true`). With `false` it runs once per daemon start |
| `env` | Extra environment variables |
| `cwd` | Working directory |
| `capture_output` | Keep stdout/stderr in the supervisor log (default `true`) |
| `enabled` | `false` skips the service (default `true`) |

Invalid entries and duplicate names are logged and skipped. An unreadable file
is logged and doesn't stop the daemon from starting.

## Synopsis

```
geenii supervisor [--socket PATH] <command>
```

## Global Options

| Option | Short | Env Var | Description |
|---|---|---|---|
| `--socket` | `-s` | `GEENII_SOCKET`, then `GEENII_PM_SOCKET` | Path to the daemon's Unix socket |

`status`, `start`, `stop`, `restart`, `logs` and `reload` exit with code 1
if the daemon isn't running or the name is unknown. `list`, `add` and
`remove` work on the file, and work without a daemon too.

## Commands

### status

```
geenii supervisor status [--json]
```

Show supervised processes: command, running or stopped, PID, uptime, whether
it restarts, and the last exit code. `--json` prints the daemon's raw status.

### start

```
geenii supervisor start <NAME> [OPTIONS] -- <CMD>...
```

Start `NAME` running `CMD` and keep it running. `CMD` is executed directly,
without a shell; use `sh -c '...'` for pipes or redirects. Put `--` before
`CMD` when the command has options of its own. If `NAME` already exists, its
configuration is replaced and takes effect at the next restart.

| Option | Short | Description |
|---|---|---|
| `--no-restart` | | Run once; don't restart the process when it exits |
| `--env` | `-e` | Environment variable in `KEY=VALUE` format (repeatable) |
| `--cwd` | `-d` | Working directory |

### stop

```
geenii supervisor stop <NAME> [--keep]
```

Stop `NAME`, including every process it started (the whole process group
receives SIGTERM, then SIGKILL after 5 seconds), and stop supervising it. With
`--keep`, the configuration stays listed as stopped, so `restart` can start it
again.

### restart

```
geenii supervisor restart <NAME>
```

Restart `NAME` now. This also resets its restart delay, and works for
processes started with `--no-restart`.

### logs

```
geenii supervisor logs <NAME> [--tail N]
```

Show the last `N` lines (default 100) of the process's output. Lines are
tagged `[stdout]`, `[stderr]` or `[supervisor]` (start, exit and restart
events). The daemon keeps the last 400 lines per process in memory.

### list

```
geenii supervisor list [--config PATH]
```

List the services declared in the file, including disabled ones.

### add

```
geenii supervisor add <NAME> [OPTIONS] -- <CMD>...
```

Declare a service in the file. If a daemon is running with this file, it
starts the service right away. Options: `--no-restart`, `--env`/`-e`
(repeatable), `--cwd`/`-d`, `--disabled`, `--config`/`-c`. Fails if `NAME` is
already in the file.

### remove

```
geenii supervisor remove <NAME> [--config PATH]
```

Remove a service from the file. If a daemon is running with this file, it
stops the service.

### reload

```
geenii supervisor reload [--config PATH]
```

Make the running daemon apply its services file, for example after editing
it by hand:

- New services start.
- Removed services stop.
- Changed services restart with the new definition.
- File services that were stopped by hand start again.

Ad-hoc services are left alone, unless the file declares a service with the
same name, in which case the file's definition takes over. Exits with code 1
if no daemon is running with this file.

## Examples

```bash
geenii supervisor add web -- python -m http.server 8000    # persistent (services.json)
geenii daemon start                                        # starts web
geenii supervisor start tmp -- python -m http.server 9000  # ad hoc
geenii supervisor start worker -e QUEUE=jobs -d ~/project -- python worker.py
geenii supervisor status
geenii supervisor logs web -n 20
geenii supervisor restart worker
geenii supervisor stop web
```
