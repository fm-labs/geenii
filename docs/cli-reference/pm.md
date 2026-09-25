# geenii pm

Manage background processes. The process manager runs inside the
[geenii daemon](daemon.md), so start that first (`geenii daemon start`).

## Synopsis

```
geenii pm [--socket PATH] <command>
```

## Global Options

| Option | Short | Env Var | Description |
|---|---|---|---|
| `--socket` | `-s` | `GEENII_SOCKET`, then `GEENII_PM_SOCKET` | Path to the daemon's Unix socket (default `$GEENII_CACHE_DIR/geenii.sock`) |

## Commands

### ping

```
geenii pm ping
```

Check if the daemon, and with it the process manager, is running. Exits with
code 1 if not reachable.

### serve

```
geenii pm serve [--socket PATH]
```

Alias for [`geenii daemon start`](daemon.md). It runs the whole daemon,
including the scheduler (with `$GEENII_DIR/scheduler.json`, if it exists) and
the supervisor. Accepts an optional `--socket`/`-s` to set the listen path.

### start

```
geenii pm start <COMMAND> [OPTIONS]
```

Start a background process. `COMMAND` is a single string that runs through
the shell, so pipes, redirects and `&&` work. Quote it as a whole:
`geenii pm start "make build > build.log 2>&1"`.

#### Options

| Option | Short | Description |
|---|---|---|
| `--cwd` | `-d` | Working directory for the process |
| `--pid` | `-p` | Custom process ID: 1–64 letters, digits, `_` or `-`, starting with a letter or digit. Must not be in use |

### status

```
geenii pm status <PROCESS_ID>
```

Check the state of a background process.

### output

```
geenii pm output <PROCESS_ID> [OPTIONS]
```

Show captured output of a background process.

#### Options

| Option | Short | Description |
|---|---|---|
| `--stream` | | Output stream: `stdout` (default) or `stderr` |
| `--tail` | `-n` | Show only the last N lines |

### wait

```
geenii pm wait <PROCESS_ID> [--timeout SECONDS]
```

Wait until the process has finished and print its final state as JSON. Exits
with the process's exit code: 1 if it was killed or orphaned, 2 if the timeout
expired, in which case the process keeps running. Works for scheduled runs too;
their IDs are shown by `geenii scheduler status`.

### kill

```
geenii pm kill <PROCESS_ID> [OPTIONS]
```

Kill a running background process, including any processes it started (the
whole process group is signalled). Waits up to 5 seconds for the process to
exit and prints its final state.

Stopping the daemon (`geenii daemon stop`, or SIGINT/SIGTERM) also
terminates all running background processes. If the daemon dies without a
clean shutdown, processes it was tracking are shown as `orphaned` after the
next start.

#### Options

| Option | Short | Description |
|---|---|---|
| `--force` | `-f` | Send SIGKILL instead of SIGTERM |

### list

```
geenii pm list [OPTIONS]
```

List background processes.

#### Options

| Option | Short | Description |
|---|---|---|
| `--all` | `-a` | Include finished processes from disk |

### cleanup

```
geenii pm cleanup <PROCESS_ID>
```

Remove on-disk logs for a finished process.

## Examples

```bash
geenii daemon start
geenii pm ping
geenii pm start "python my_script.py" -d /tmp
geenii pm list -a
geenii pm output my-proc -n 20
geenii pm kill my-proc -f
geenii pm cleanup my-proc
```
