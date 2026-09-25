# Process Management: Supervisor, Scheduler, Process Manager

Geenii has three separate building blocks that start and manage external
processes. They overlap a little, but each solves a different problem:

| Component | Module | Model | Runs as | Used by |
|---|---|---|---|---|
| **Supervisor** | `geenii/supervisor.py` | Desired state: keep long-lived processes up and restart them when they exit | Library (asyncio), embedded in a host process | The server repository (`/api/v1/supervisor/*`, consumed by `data/apps/geenii-supervisor`). Nothing in this repo calls it. |
| **Scheduler** | `geenii/scheduler.py` | Time-based: run a command or Python callable on a cron schedule or once at a set time | Standalone daemon (`geenii-scheduler`, `geenii scheduler start`) or embedded | CLI, cron-style agent runs |
| **Process Manager** | `geenii/pm/` | Fire and forget: start a background job, get an ID back, check its state and output later | Unix-socket JSON-RPC service plus a synchronous client | `ProcessingAgent` (the `bg_process_*` tools), `geenii pm` CLI |

Rule of thumb:

- A process that should **always be running** belongs in the **Supervisor**.
- A process that should **run at certain times** belongs in the **Scheduler**.
- A process that an **agent or user starts on demand** and checks on later belongs in the **Process Manager**.

For how to configure and use the scheduler, see the user guide page
[Scheduler](../user-guide/scheduler.md). For the `geenii pm` and
`geenii scheduler` commands, see the [CLI reference](../cli-reference/index.md).

---

## Supervisor

`geenii/supervisor.py` is an asyncio process supervisor. You declare which
processes should be running with `ensure()`. A **watcher task** for each
process then keeps reality matching that declaration: it spawns the process,
waits for it to exit, and restarts it with a delay (backoff).

All public methods are coroutines or plain methods that must run on the same
event loop. They are designed to be called from concurrent FastAPI handlers.

### Data model

| Type | Purpose |
|---|---|
| `ProcConfig` | The declared (desired) state: `name`, `cmd: list[str]`, `restart=True`, `env` (extra variables, merged into `os.environ`), `cwd`, `capture_output=True` |
| `UpdateProcRequest` | Pydantic model for partial updates: `restart`, `env`, `cwd` |
| `ProcRuntime` | The live state: the `asyncio.subprocess.Process`, `started_at`, `last_exit`, and the stdout/stderr pipe tasks |
| `RunResult` | Result of a one-shot `run()`: `returncode`, `stdout`/`stderr` as lists of lines, `duration_s` |
| `LogEvent` | One log line: `t` (unix time), `name`, `tag` (`stdout` / `stderr` / `supervisor`), `msg`. `as_text()` returns `"[tag] msg"` and `as_json()` returns a compact JSON line |
| `LogBus` | A ring buffer of `LogEvent`s for each process (400 lines by default) that also fans events out to subscriber queues. Each queue holds at most `SUBSCRIBER_QUEUE_SIZE` (1000) events; when a slow subscriber falls behind, its oldest events are dropped |

Internal state is held in five dicts, all keyed by process name:
`_configs` (desired state), `_runtime` (live processes), `_watchers`
(watcher tasks), `_logs` (log buses) and `_backoff` (current restart delay).
The backoff is kept outside `ProcRuntime` because the runtime entry is removed
every time the process exits. An `asyncio.Lock` serializes changes to
configuration and lifecycle.

Tuning constants at module level:

| Constant | Default | Meaning |
|---|---|---|
| `BACKOFF_INITIAL` | `0.5` | Restart delay after a clean exit or the first crash |
| `BACKOFF_MAX` | `30.0` | Upper bound for the doubling restart delay |
| `BACKOFF_RESET_AFTER` | `60.0` | A process that stayed up this many seconds before crashing starts again from `BACKOFF_INITIAL` |
| `RUN_LOG_HISTORY` | `50` | Number of finished `run()` log buffers kept |
| `SUBSCRIBER_QUEUE_SIZE` | `1000` | Maximum events queued for each log subscriber |
| `TERMINATE_GRACE_S` | `5.0` | Delay between `SIGTERM` and `SIGKILL` when terminating a process |

### Lifecycle

```
ensure(name, cfg)
  └─ _configs[name] = cfg; create LogBus; start watcher if none is alive
       │
       ▼
  _watch(name)  ── loops until the stop event is set or the config is removed
       ├─ not running → _spawn()
       │     ├─ create_subprocess_exec(cmd, env=os.environ ∪ cfg.env, cwd, start_new_session=True)
       │     ├─ _runtime[name] = ProcRuntime(...)
       │     └─ if capture_output: _pipe() tasks copy stdout/stderr to the LogBus
       │     (if spawn raises: log it, sleep the current backoff, double it)
       │
       └─ running → await proc.wait()
             ├─ record last_exit, log "exited rc=N"
             ├─ stopping, config removed, or restart=False → drop runtime, return
             └─ otherwise: delay = _next_delay(rc, uptime); sleep(delay); respawn
```

`_next_delay()` sets the restart delay:

- **Clean exit (`rc == 0`)** or **uptime ≥ `BACKOFF_RESET_AFTER`**: the
  backoff resets to `BACKOFF_INITIAL`.
- **Non-zero exit:** the process waits the current backoff, and the stored
  backoff doubles, up to `BACKOFF_MAX`. A process that keeps crashing
  therefore waits 0.5s, 1s, 2s, … and then 30s between attempts.

Every process is started in its **own process group**
(`start_new_session=True`), the same way the Scheduler and the Process Manager
do it. Signals go to the whole group, so processes started by the command are
stopped too. This covers the members of `sh -c "a | b"`, for example, or
anything the command put in the background.

Termination (`_terminate_one`) cancels the log pipe tasks and sends `SIGTERM`
to the group. After waiting up to `TERMINATE_GRACE_S` for the process to exit,
it sends `SIGKILL` to the group.

### Public API

| Method | Behavior |
|---|---|
| `await ensure(name, cfg)` | Registers or replaces the config and makes sure a watcher is running. Replacing the config of a running process does **not** restart it; the new `cmd` takes effect at the next restart. |
| `await stop_process(name, disable_restart=True)` | Cancels the watcher and terminates the process. With `disable_restart=True` the config is removed as well. With `False` the config stays in `status()["desired"]`, but nothing respawns the process until `ensure()` or `restart_process()` is called. |
| `await restart_process(name)` | Cancels the watcher, terminates the process, resets the backoff and starts a new watcher, which spawns the process right away. This also works when `restart=False`. Raises `KeyError` for unknown names. |
| `await update_config(name, req)` | Partial update. `env` and `cwd` change only if they are present in the request body (`model_fields_set`); an explicit `null` clears them. Takes effect at the next spawn. |
| `status()` | Returns `{"desired": {...}, "running": {...}, "watchers": {...}}`. Env **values** are never exposed, only `env_keys`. |
| `logs(name, tail=100)` | The last `tail` log lines as text. |
| `stream_logs(name)` | Async iterator: replays the buffer, then yields live lines. Every 15 seconds without output it yields `""` as a keepalive, which the HTTP route turns into an SSE comment. |
| `stream_logs_jsonl(name)` | The same, but yields `LogEvent` objects, with `None` as the keepalive. |
| `await run(cmd, env=, cwd=, timeout=, name=)` | One-shot command that is **not** part of the desired state. Output goes to a LogBus (so it can be streamed live) and is returned as a `RunResult`. On timeout, or when the caller cancels the coroutine, the process group is sent `SIGKILL` and the exception is raised again. Only the last `RUN_LOG_HISTORY` finished jobs keep their LogBus. Older ones are removed, unless a supervised process has the same name. |
| `await stop()` | Sets the stop event, cancels all watchers and terminates all processes. |
| `is_active()` | `True` while any process is running or any watcher task is alive. Useful for graceful-shutdown loops. |

### Example

```python
sup = Supervisor()
await sup.ensure("worker", ProcConfig(name="worker", cmd=["python", "worker.py"]))
await sup.ensure("once", ProcConfig(name="once", cmd=["sh", "-c", "echo hi"], restart=False))

print(sup.status())
async for line in sup.stream_logs("worker"):
    ...

await sup.stop()
```

When `capture_output=False`, the child inherits the host's stdout and stderr,
and only `supervisor`-tagged lines reach the LogBus. Every line is also
written to the Python logger at `INFO` level as `[name][tag] msg`.

---

## Scheduler

`geenii/scheduler.py` runs tasks on a cron schedule (`cron:EXPR`) or once at a
set time (`at:ISO_DATETIME`). Task definitions come from a JSON file (by
default `$GEENII_DIR/scheduler.json`) or are added programmatically. Config
format and usage are covered in the [user guide](../user-guide/scheduler.md);
this section covers the internals.

### Components

| Item | Purpose |
|---|---|
| `parse_interval(s)` | Returns `("cron", expr)` or `("at", iso)`. Raises `ValueError` for an invalid cron expression, a bad datetime, or an unknown prefix. |
| `SchedulerConfig` | Pydantic schema for one config entry (`extra="allow"`, so unknown keys are ignored). `timeout` must be greater than 0. |
| `ScheduledTask` | Dataclass for a runtime task: `name`, `interval`, `cmd` **or** `module` **or** `run_fn`, `params`, `enabled`, `env`, `working_dir`, `timeout`, `allow_overlap` |
| `ScheduledTask.load()` | Validates the interval, resolves `module` (`"pkg.mod.fn"`) to a callable, and works out how the callable is called (see below). Raises `TypeError` for callables whose signature is not supported. |
| `ScheduledTask.next_run(after)` | For `at:` tasks, the fixed datetime converted to UTC. For `cron:` tasks, the next croniter match after `after` (default: now, UTC). |
| `ScheduledTask.run()` | Runs the task under `asyncio.wait_for(..., timeout)`. Failures and timeouts are caught and logged. **Cancellation is passed on**, so the subprocess cleanup can run. |
| `Scheduler` | Loads the config, runs the main loop, and supports adding and removing tasks at runtime. |
| `serve(scheduler)` | Installs SIGINT and SIGTERM handlers, starts the scheduler and waits until it has stopped. Used by both `main()` and `geenii scheduler start`. |

Module constants: `TERMINATE_GRACE_S` (5s, the delay between SIGTERM and
SIGKILL) and `STREAM_LINE_LIMIT` (1 MiB, the maximum length of one output
line).

### Execution of `cmd` tasks

1. Each argument is expanded with `os.path.expandvars` (for example `$GEENII_BIN`).
2. `env` is merged over `os.environ`, and `working_dir` becomes `cwd`.
3. The process is started with `start_new_session=True`, which puts it in its
   own process group.
4. stdout and stderr are read line by line and logged immediately (stdout at
   INFO, stderr at WARNING), so output is never buffered as a whole.
5. A non-zero exit becomes a `RuntimeError`, which `run()` catches and logs.
6. If the run is cancelled (by a timeout or by `stop()`), `_terminate()` sends
   `SIGTERM` to the **process group**. After `TERMINATE_GRACE_S` it sends
   `SIGKILL`. Child processes of the command are stopped too.

### Execution of callables

`load()` inspects the callable's signature:

- If it can be called as `fn(params, env)`, it is called that way, with
  `params or []` and `env`.
- If it takes no arguments, it is called as `fn()`.
- Any other signature is rejected with `TypeError`.

Async callables are awaited. Sync callables run in the default executor. A
timeout or `stop()` cancels async callables, but a sync callable keeps running
in its thread, because Python threads can't be interrupted.

### Main loop

```
start() → clear stop event; asyncio.create_task(_run())

_run():
  _schedule[name] = task.next_run()        for every task at startup
  every 1 second:
    with _lock:
      for each task:
        if now >= _schedule[name]:
          previous run still active and not allow_overlap → log warning, skip
          otherwise → _launch(task)         (tracked in _running_tasks and _active[name])
          at:   → mark for removal
          cron: → _schedule = next_run(after=now)
      remove finished one-shot tasks
```

Behavior that follows from this design:

- **Resolution** is about 1 second. Due tasks are started as independent
  asyncio tasks, so a slow task does not block the loop.
- **No catch-up.** If the host sleeps or the loop stalls, a missed cron slot
  runs once and the next time is computed from *now*.
- **Overlap protection.** By default a cron slot is skipped while the
  previous run of the same task is still going. `allow_overlap=True` turns
  this off.
- **An `at:` time in the past** runs immediately on startup.
- **Cron expressions are evaluated in UTC.**
- **Names are unique.** `load_config()` skips duplicate names with an error,
  and `add_task()` raises `ValueError`.

### Lifecycle and shutdown

- `start()` raises only if the main loop is still running. A stopped
  scheduler can be started again.
- `stop()` sets the stop event and cancels the main loop and every running
  task. For `cmd` tasks, cancellation terminates the process group.
- `wait_until_stopped()` waits for the main loop and gathers the running
  tasks. This includes waiting for the subprocess cleanup to finish.
- `main()` (the `geenii-scheduler <config>` entry point) initializes logging,
  loads the config and calls `serve()`. `geenii scheduler start` loads the
  config once and passes the scheduler to `serve()`.

`Scheduler.status` returns the following:

- for each task: its name and interval, next and last run times (ISO), and a
  `running` flag
- the number of running tasks
- the overall state, `running` or `stopped`

---

## Process Manager

`geenii/pm/` provides a way to run commands in the background. The commands
outlive the caller (the agent or CLI call that started them), and their output
is saved to files on disk. It has three layers:

```
ProcessingAgent / geenii pm CLI
        │  ProcessManagerClient (sync, one connection per call)
        ▼
  Unix socket  $GEENII_CACHE_DIR/process_manager.sock   (newline-delimited JSON)
        │
  ProcessManagerService (asyncio server; each RPC runs in the thread-pool executor)
        │
  ProcessManager (subprocess.Popen + threads)
        │
  $GEENII_CACHE_DIR/processes/<pid>/{meta.json, stdout.log, stderr.log}
```

The service has to be running before the client can be used:

```bash
geenii pm serve
```

It can also be started with `python -m geenii.pm.process_manager_service [socket]`.

### Commands: shell or no shell

The type of `cmd` decides how the command is executed:

| `cmd` type | Execution | Use for |
|---|---|---|
| `str` | Through the shell (`/bin/sh -c`, via `shell=True`) | Command lines with pipes, redirects, `&&`, `cd`, `$VAR`. This is what the agent tool and `geenii pm start` send |
| `list[str]` | Directly, without a shell. Each element is one argument | Programmatic callers that build an argument vector; nothing is interpreted by a shell |

The shell is used on purpose for strings. The caller supplies the **whole**
command, so the shell grants nothing beyond what running any program already
allows. Protection comes from the agent's tool approval (HITL) and the skill
tool filters, not from avoiding the shell.

One caveat: an argument filter such as `bg_process_start(command:uname *)`
only checks the start of the string. Anything chained after it, for example
`uname; …`, still runs.

`ProcessInfo.shell` records which of the two modes was used.

### ProcessManager (`process_manager.py`)

A thread-based, synchronous manager. Each process gets a short ID: 12 hex
characters, or a caller-supplied `pid`. That ID is separate from the OS
`system_pid`.

Process IDs become directory names, so they are validated. An ID must be 1–64
characters long, may contain only letters, digits, `_` and `-`, and must start
with a letter or digit. Anything else, including `..` or path separators,
raises `ValueError`. Reusing an ID that exists in memory or on disk is
rejected as well. An empty `pid` means "auto-generate".

| Method | Behavior |
|---|---|
| `start(cmd, env=, cwd=, pid=)` | Validates `cmd` and `pid`, then calls `Popen(..., start_new_session=True)` so the command gets its own process group. Starts two daemon threads that append each pipe to its log file line by line (flushing after each line), and a waiter thread. Writes `meta.json` and returns `ProcessInfo` with state `running`. |
| `status(pid)` | Answers from memory while the process runs, otherwise from `meta.json`. Raises `KeyError` if the ID is unknown. Never creates files. |
| `output(pid, stream="stdout", tail=None)` | Returns the log contents, or only the last `tail` lines. Works while the process is still running. `stream` must be `stdout` or `stderr`. |
| `kill(pid, force=False)` | Sends `SIGTERM` (or `SIGKILL` with `force`) to the **process group**, so child processes are signalled as well. Waits up to `KILL_WAIT_S` (5s) for the exit, so the returned state is normally already `killed`. |
| `list(include_finished=False)` | Processes in memory, plus finished ones from disk if requested, newest first. |
| `cleanup(pid)` | Runs `rmtree` on the process directory. Refuses while the process is still tracked. |
| `shutdown()` | Terminates all running processes (process group `SIGTERM`, then `SIGKILL` after `TERMINATE_GRACE_S`) and records their final state. Called by `ProcessManagerService.stop()`. |

The waiter thread sets the final state from the return code:

| Condition | State |
|---|---|
| exit code `0` | `completed` |
| killed by a signal (`< 0`), or non-zero after `kill()`/`shutdown()` | `killed` |
| any other non-zero exit | `failed` |

It then rewrites `meta.json` (atomically, via a temporary file and
`os.replace`) and removes the process from memory. `meta.json` stores only env
**keys**; env values stay in memory.

**Orphans.** When a `ProcessManager` is created, it looks for `meta.json`
files still in the `running` (or `pending`) state. That only happens if the
previous service was killed without a clean shutdown. Those processes are
marked `orphaned`, with an explanation in `error`: their output is no longer
captured, and whether they are still running is unknown. They are not
signalled, because their OS pid may have been reused by another process.

### Wire protocol (`process_manager_service.py`)

Each request and response is one JSON object followed by a newline. A single
connection may send several requests.

```json
→ {"method": "start", "params": {"command": "sleep 5; echo done", "cwd": null, "pid": null, "env": null}}
← {"ok": true, "result": {"pid": "a1b2c3d4e5f6", "shell": true, "state": "running", ...}}
← {"ok": false, "error": "KeyError: 'Unknown process: xyz'"}
```

| Method | Params | Result |
|---|---|---|
| `ping` | none | `"pong"` |
| `start` | `command` (string, or list of strings), `env?`, `cwd?`, `pid?` | `ProcessInfo` dict |
| `status` | `process_id` | `ProcessInfo` dict |
| `output` | `process_id`, `stream?`, `tail?` (a value of 0 or less means all output) | string |
| `kill` | `process_id`, `force?` | `ProcessInfo` dict |
| `list` | `include_finished?` | list of `ProcessInfo` dicts |
| `cleanup` | `process_id` | `"ok"` |

Errors raised by a handler are returned as `"<ExceptionType>: <message>"`.
The socket has no authentication; access is controlled only by the socket
file's permissions (the process umask).

On SIGINT or SIGTERM the service stops accepting connections, terminates all
running processes via `shutdown()`, and removes the socket file.

### Client (`process_manager_client.py`)

`ProcessManagerClient(socket_path)` is stateless. Each call opens a new
connection, sends one request, reads up to the first newline, and closes the
connection. If the response has `"ok": false`, the client raises
`RuntimeError(error)`. `is_available()` checks that the socket file exists and
that `ping` succeeds. The client has no socket timeout.

### Integration

- `ProcessingAgent` (`geenii/agents.py`) creates a client and registers the
  tools from `geenii/core/process_tools.py`: `bg_process_start`,
  `bg_process_status`, `bg_process_output`, `bg_process_kill` and
  `bg_process_list`.
  - `bg_process_start` sends the command as a string, so it runs through the
    shell.
  - If no `working_directory` is given, it defaults to `GEENII_WORKING_DIR`,
    the same directory the `bash` tool uses. Without this default, the command
    would run in the directory `geenii pm serve` was started from.
  - Errors (for example an invalid ID) are returned to the model as
    `{"error": ...}`.
- `geenii pm` (`cli/pm_cli.py`) provides `serve`, `ping`, `start`, `status`,
  `output`, `kill`, `list` and `cleanup`. The socket path can be overridden
  with `--socket` or `GEENII_PM_SOCKET`.

---

## Known issues

No open issues are currently tracked for these components.

Remaining limits:

- **Scheduler:** a timeout can't interrupt a sync `module` callable, which
  keeps running in its worker thread.
- **Process Manager:** skill argument filters on `command` arguments can be
  bypassed with shell syntax (see
  [Commands: shell or no shell](#commands-shell-or-no-shell)). This is being
  tracked as a separate `ToolFilter` fix.
