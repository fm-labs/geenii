# geenii daemon

Run and control the geenii daemon: one background process that hosts the
process manager, the scheduler and the supervisor behind a single Unix socket.

## Synopsis

```
geenii daemon <command> [--socket PATH]
```

## Socket

All subcommands accept `--socket`/`-s`. If it isn't given, the path comes from
`GEENII_SOCKET`, then from `GEENII_PM_SOCKET` (kept for compatibility), and
otherwise defaults to `$GEENII_CACHE_DIR/geenii.sock`. `geenii pm` uses the
same socket.

## Commands

### start

```
geenii daemon start [--socket PATH] [--scheduler-config PATH] [--services-config PATH]
```

Run the daemon in the foreground until SIGINT/SIGTERM or `geenii daemon stop`.

- `--scheduler-config`/`-c`: the tasks to schedule. Default:
  `$GEENII_WORKING_DIR/.geenii/scheduler.json`. If the file doesn't exist, the scheduler runs
  without tasks.
- `--services-config`: the services to supervise
  (see [supervisor](supervisor.md#servicesjson)). Default:
  `$GEENII_WORKING_DIR/.geenii/services.json`. If the file doesn't exist, no services start.
- Startup order: process-manager recovery, then services, then the scheduler,
  and only then does the daemon accept connections.
- Only one daemon can run per socket. Starting a second one fails with an
  error; a stale socket file left by a crashed daemon is replaced.

### status

```
geenii daemon status [--socket PATH]
```

Print the daemon's PID, socket, uptime, and a summary of each component as
JSON. Exits with code 1 if the daemon isn't running.

### stop

```
geenii daemon stop [--socket PATH]
```

Ask the running daemon to shut down. It stops scheduling, then terminates
supervised processes and running background processes, and records their
final state.

## Aliases

These older commands now start the daemon:

| Command | Equivalent |
|---|---|
| `geenii pm serve [--socket PATH]` | `geenii daemon start [--socket PATH]` |
| `geenii scheduler start [--config PATH]` | `geenii daemon start --scheduler-config PATH` |
| `geenii-scheduler CONFIG` | `geenii daemon start --scheduler-config CONFIG` |

Both aliases start the whole daemon. In particular, `geenii pm serve` now also
runs the tasks in `$GEENII_WORKING_DIR/.geenii/scheduler.json` if that file exists.

## Examples

```bash
geenii daemon start
geenii daemon status
geenii pm start "sleep 60"
geenii daemon stop
```

## Related Entry Points

- `geenii-daemon [--socket PATH] [--scheduler-config PATH]` runs the daemon
  without the rest of the CLI.
