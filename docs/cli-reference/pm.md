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
| `--socket` | `-s` | `GEENII_SOCKET`, then `GEENII_PM_SOCKET` | Path to the daemon's Unix socket (default `$GEENII_CACHE_DIR/geeniid.sock`) |

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
including the scheduler (with `~/.geenii/scheduler.json`, if it exists) and
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
| `--offset` | | Start reading at this byte position (default 0) |
| `--limit` | | Read at most this many bytes |

`--offset`/`--limit` read the output in chunks; they can't be combined with
`--tail`. To read all of a large output, increase `--offset` by `--limit`
until nothing is printed. A UTF-8 character that crosses a chunk boundary is
printed whole with the chunk that holds its first byte.

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

### gc

```
geenii pm gc [--max-age AGE] [--state STATE ...] [--dry-run]
```

Remove the on-disk logs of all processes that finished longer ago than
`--max-age`, oldest first, and print their IDs. Running processes, processes
the daemon still tracks, and directories without a `meta.json` (a process
being started) are never removed. Garbage collection only runs when you call
it; the daemon doesn't do it on its own.

#### Options

| Option | Short | Description |
|---|---|---|
| `--max-age` | | Minimum time since the process finished: seconds, or a number with `s`, `m`, `h`, `d` or `w` (e.g. `12h`, `7d`). Default: `GEENII_PM_GC_MAX_AGE` (seconds), or 7 days |
| `--state` | | Only collect processes in this state: `completed`, `failed`, `killed` or `orphaned`. Repeatable. Default: `completed`, `failed` and `killed` |
| `--dry-run` | `-n` | Only list what would be removed |

## Examples

```bash
geenii daemon start
geenii pm ping
geenii pm start "python my_script.py" -d /tmp
geenii pm list -a
geenii pm output my-proc -n 20
geenii pm kill my-proc -f
geenii pm cleanup my-proc
geenii pm output my-proc --offset 0 --limit 65536   # first 64 KiB
geenii pm gc --max-age 2d --dry-run                 # what would be removed
geenii pm gc --state orphaned --max-age 0
```
