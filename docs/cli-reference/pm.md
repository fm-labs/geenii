# geenii pm

Manage background processes via a Unix-socket process manager service.

## Synopsis

```
geenii pm [--socket PATH] <command>
```

## Global Options

| Option | Short | Env Var | Description |
|---|---|---|---|
| `--socket` | `-s` | `GEENII_PM_SOCKET` | Path to the process manager Unix socket |

## Commands

### ping

```
geenii pm ping
```

Check if the process manager service is running. Exits with code 1 if not
reachable.

### serve

```
geenii pm serve [--socket PATH]
```

Start the process manager service. Accepts an optional `--socket`/`-s` to set
the listen path.

### start

```
geenii pm start <COMMAND> [OPTIONS]
```

Start a background process.

#### Options

| Option | Short | Description |
|---|---|---|
| `--cwd` | `-d` | Working directory for the process |
| `--pid` | `-p` | Custom process ID |

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

### kill

```
geenii pm kill <PROCESS_ID> [OPTIONS]
```

Kill a running background process.

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
geenii pm serve
geenii pm ping
geenii pm start "python my_script.py" -d /tmp
geenii pm list -a
geenii pm output my-proc -n 20
geenii pm kill my-proc -f
geenii pm cleanup my-proc
```
