# Process Management: Supervisor, Scheduler, Process Manager

Geenii has three building blocks that start and manage external processes.
Each solves a different problem, and all three run inside one process, the
[geenii daemon](#the-geenii-daemon-geeniidaemon):

| Component | Module | Model | Runs as | Used by |
|---|---|---|---|---|
| **Supervisor** | `geenii/supervisor.py` | Desired state: keep long-lived processes up and restart them when they exit | Inside the daemon (`supervisor.*` methods) | `geenii supervisor` CLI and `supervisor.*` RPC. The [server](server.md)'s `/api/v1/supervisor/*` routes (used by `data/apps/geenii-supervisor`) are currently disabled |
| **Scheduler** | `geenii/scheduler.py` | Time-based: run a command or Python callable on a cron schedule or once at a set time | Inside the daemon, with tasks from `scheduler.json` | CLI, cron-style agent runs, `scheduler.*` RPC |
| **Process Manager** | `geenii/pm/` | Fire and forget: start a background job, get an ID back, check its state and output later | Inside the daemon (`pm.*` methods), plus a synchronous client | `ProcessManagerAgent` (the `bg_process_*` tools), `geenii pm` CLI |

Rule of thumb:

- A process that should **always be running** belongs in the **Supervisor**.
- A process that should **run at certain times** belongs in the **Scheduler**.
- A process that an **agent or user starts on demand** and checks on later belongs in the **Process Manager**.

For how to configure and use the scheduler, see the user guide page
[Scheduler](../user-guide/scheduler.md). For the `geenii daemon`, `geenii pm`
and `geenii scheduler` commands, see the [CLI reference](../cli-reference/index.md).

---

## The geenii daemon (`geenii/daemon/`)

All three components run inside **one process**, the geenii daemon, on one
event loop. They are reached through **one Unix socket**.

```
 agents (ProcessManagerClient) · geenii pm / daemon CLI · other DaemonClient users
        │  DaemonClient (sync, one connection per call)
        ▼
  Unix socket  $GEENII_CACHE_DIR/geenii.sock   (newline-delimited JSON-RPC)
        │
  DaemonServer (daemon/server.py): socket, dispatch, lifecycle
        │
  ProcessHost (daemon/host.py): owns the components, registers their RPC methods
        ├── ProcessManager   pm.*
        ├── Scheduler        scheduler.*   (tasks from $GEENII_DIR/scheduler.json)
        └── Supervisor       supervisor.*
```

| Module | Contents |
|---|---|
| `daemon/client.py` | `DaemonClient` with `call(method, params)`, `is_available()`, `info()` and `shutdown()`. Also `default_socket_path()`: `GEENII_SOCKET`, then `GEENII_PM_SOCKET`, then `$GEENII_CACHE_DIR/geenii.sock`. It imports nothing heavy, so agents can use it cheaply. |
| `daemon/host.py` | `ProcessHost(pm=, scheduler=, supervisor=, scheduler_config=, services_config=)`. `scheduler_config` and `services_config` are the files that `scheduler.reload` and `supervisor.reload` re-read. `start()` runs `pm.recover()`, applies the services file (if one exists; errors are logged, not fatal), then starts the scheduler loop. `stop()` stops, in order: the scheduler (its running tasks are cancelled and their processes killed), then the supervised processes, then `pm.shutdown()`. `methods` maps RPC names to coroutines. |
| `daemon/server.py` | `DaemonServer(host, socket_path)`, `build_host(scheduler_config)`, `run_daemon()` and `main()`, which is the `geenii-daemon` entry point. |

**Starting.** Run `geenii daemon start [--socket] [--scheduler-config]`.
The following are aliases for it:
- `geenii pm serve`
- `geenii scheduler start`
- `geenii-scheduler CONFIG`
- `geenii-daemon`
- `python -m geenii.pm.process_manager_service`

Only one daemon can own a socket. If the socket file exists and something
answers on it, `start()` raises `DaemonAlreadyRunning`. A stale file with
nothing listening is replaced.

**Stopping.** Stop the daemon with `geenii daemon stop` (RPC
`daemon.shutdown`) or with SIGINT/SIGTERM. The server first stops accepting
connections, then calls `ProcessHost.stop()`, then removes the socket file.

### CLI

| Command group | Talks to the daemon | Without a daemon |
|---|---|---|
| `geenii daemon` | `start`, `status`, `stop` | `status` and `stop` exit with code 1 |
| `geenii pm` | every command except `serve` (an alias of `daemon start`) | Commands fail; `ping` exits with code 1 |
| `geenii scheduler` | `status` (live table), `run` (starts in the daemon), `add`/`remove` (edit the file, then `scheduler.reload`), `reload` | Works on the config file: offline `status`, local `run`, and file edits only. The same fallback applies when the daemon uses a different config file |
| `geenii supervisor` | `status`, `start`, `stop`, `restart`, `logs` | Commands exit with code 1 |

### Wire protocol

Each request and response is one JSON object followed by a newline. A single
connection may send several requests.

```json
→ {"method": "pm.start", "params": {"command": "sleep 5; echo done"}}
← {"ok": true, "result": {"pid": "a1b2c3d4e5f6", "shell": true, "state": "running", ...}}
← {"ok": false, "error": "KeyError: 'Unknown process: xyz'"}
```

| Method | Params | Result |
|---|---|---|
| `ping` | none | `"pong"` |
| `daemon.info` | none | `pid`, `socket`, `uptime_s`, plus a summary for `pm`, `scheduler` and `supervisor`, each of the last two with its `config` path |
| `daemon.shutdown` | none | `"shutting down"` (the daemon stops right after replying) |
| `pm.start` | `command` (string, or list of strings), `env?`, `cwd?`, `pid?` | `ProcessInfo` dict |
| `pm.status` | `process_id` | `ProcessInfo` dict |
| `pm.output` | `process_id`, `stream?`, `tail?` (a value of 0 or less means all output) | string |
| `pm.wait` | `process_id`, `timeout?` | Final `ProcessInfo` dict once the process has finished. Fails with `TimeoutError` after `timeout` seconds; the process keeps running |
| `pm.kill` | `process_id`, `force?` | `ProcessInfo` dict |
| `pm.list` | `include_finished?` | list of `ProcessInfo` dicts |
| `pm.cleanup` | `process_id` | `"ok"` |
| `scheduler.status` | none | `Scheduler.status` (live: next and last run, `running` flag per task) |
| `scheduler.run` | `name` | `"started"`. Starts a run now via `Scheduler.run_now()`, without waiting for it. Fails for unknown tasks, or if the task is still running and doesn't allow overlap |
| `scheduler.reload` | none | `{"added": [...], "removed": [...], "updated": [...]}`. Re-reads the daemon's scheduler config via `Scheduler.reload_config()`. Fails if the daemon was started without a config file |
| `supervisor.status` | none | `Supervisor.status()` |
| `supervisor.ensure` | `name`, `cmd` (list of strings), `restart?`, `env?`, `cwd?`, `capture_output?` | `"ok"` |
| `supervisor.stop` | `name`, `disable_restart?` (default `true`) | `"ok"` |
| `supervisor.restart` | `name` | `"ok"` |
| `supervisor.logs` | `name`, `tail?` (default 100) | list of log lines |
| `supervisor.reload` | none | `{"started": [...], "stopped": [...], "restarted": [...]}`. Applies the daemon's services file via `Supervisor.apply_services()`. Fails if the daemon has no services config or the file is missing or invalid |

`start`, `status`, `output`, `kill`, `list` and `cleanup` without a prefix
are aliases of the `pm.*` methods, left over from the former standalone
process manager service.

Errors raised by a handler are returned as `"<ExceptionType>: <message>"`.
The socket has no authentication. Access is controlled only by the socket
file's permissions (the process umask), and anyone who can connect can run
commands.

---

## Shared helpers (`geenii/proc.py`)

Low-level building blocks shared by all three components. They define the
common conventions:

- Extra environment variables are merged over `os.environ`.
- Every child runs in its own process group.
- Termination is `SIGTERM` to the group, a grace period, then `SIGKILL`.

| Helper | Purpose |
|---|---|
| `merged_env(extra)` | Copy of `os.environ` with `extra` applied on top |
| `await spawn(cmd, env=, cwd=, capture_output=True, stdout=, stderr=)` | `create_subprocess_exec` with `start_new_session=True`. `cmd` is an argument vector; no shell is involved. `stdout`/`stderr` accept an explicit target, such as an open log file, instead of a pipe |
| `shell_argv(command)` | `["/bin/sh", "-c", command]`, for running a command line through the shell with `spawn()` |
| `await terminate(proc, grace=5.0)` | `SIGTERM` to the group, wait up to `grace` seconds, then `SIGKILL` to the group. Returns the exit code; a process that has already exited is left alone |
| `terminate_sync(popen, grace=5.0)` | The same for a blocking `subprocess.Popen` |
| `signal_group(proc, sig)` | Signals the process group; works for asyncio processes and `Popen`, and ignores processes that have already exited |
| `await pump_lines(stream, on_line)` | Reads a stream to EOF and calls `on_line(str)` for each decoded line |
| `add_shutdown_handlers(on_signal)` | Calls `on_signal` on SIGINT or SIGTERM; used by the geenii daemon |

On platforms without `os.killpg`, `USE_PROCESS_GROUPS` is `False`, and the
helpers signal the direct child only.

Note that on Python 3.12+ asyncio's `proc.wait()` also waits for the output
pipes to close. A leftover child that holds the pipes open therefore delays
`wait()` until it exits. This is one reason to signal the whole group.

**Status:** the module is tested in `tests/geenii/test_proc.py`.

All three components use it, and none of them keeps its own copy of this
logic:

- **Process Manager:** `spawn`, `shell_argv`, `signal_group`, `terminate`,
  `add_shutdown_handlers`
- **Supervisor:** `spawn`, `pump_lines`, `signal_group`, `terminate`
- **Scheduler:** `spawn`, `pump_lines`, `terminate`, `add_shutdown_handlers`

`terminate_sync` currently has no caller; it's kept for `Popen`-based code.

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
| `TERMINATE_GRACE_S` | `5.0` (from `proc.TERMINATE_GRACE_S`) | Delay between `SIGTERM` and `SIGKILL` when terminating a process |

### Lifecycle

```
ensure(name, cfg)
  └─ _configs[name] = cfg; create LogBus; start watcher if none is alive
       │
       ▼
  _watch(name)  ── loops until the stop event is set or the config is removed
       ├─ not running → _spawn()
       │     ├─ proc.spawn(cmd, env=cfg.env, cwd, capture_output)   (own process group)
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

Termination (`_terminate_one`) cancels the log pipe tasks and calls
`proc.terminate()`. That sends `SIGTERM` to the group, waits up to
`TERMINATE_GRACE_S` for the process to exit, then sends `SIGKILL` to the
group.

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
| `await run(cmd, env=, cwd=, timeout=, name=)` | One-shot command that is **not** part of the desired state. Output goes to a LogBus (so it can be streamed live) and is returned as a `RunResult`. On timeout, or when the caller cancels the coroutine, the process group is sent `SIGKILL` and the exception is raised again. If the command can't be started (for example, the binary doesn't exist), the error is logged to the job's LogBus and raised. Only the last `RUN_LOG_HISTORY` finished jobs keep their LogBus. Older ones are removed, unless a supervised process has the same name. |
| `await stop()` | Sets the stop event, cancels all watchers and terminates all processes. |
| `is_active()` | `True` while any process is running or any watcher task is alive. Useful for graceful-shutdown loops. |

### Services config file

`services.json` (format in the
[supervisor CLI reference](../cli-reference/supervisor.md#servicesjson)) declares
services that the daemon starts at startup.

| Item | Purpose |
|---|---|
| `ServiceConfig` | Pydantic schema for one entry: `name`, `cmd`, `restart`, `env`, `cwd`, `capture_output`, `enabled` |
| `read_services(path)` | Parses the file into `ProcConfig`s. Expands `$VAR` in `cmd`/`cwd` and `~` in `cwd`. Invalid entries, disabled services and duplicate names are logged and skipped. A missing file or bad JSON raises |
| `await apply_services(configs)` | Makes the file-declared services match `configs` and returns `{"started", "stopped", "restarted"}` |

`apply_services()` keeps a snapshot (`_configured`) of the services it applied
last. It compares the file against that snapshot, not against the live
configuration:

- **started:** services that are new in the file, and file services that are
  currently not desired (for example stopped with `stop_process()`)
- **stopped:** services removed from the file (`stop_process()`, which also
  removes their config)
- **restarted:** services whose definition changed. They are `ensure()`d with
  the new config and restarted, so the change applies immediately. An ad-hoc
  service that the file now declares under the same name is taken over this
  way.

Services created with `ensure()` that aren't in the file are never touched.
`status()` marks each desired process with `"source": "config"` or `"api"`.

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
| `ScheduledTask.run(pm)` | Runs the task under `asyncio.wait_for(..., timeout)`. `cmd` tasks need a `ProcessManager`, and run without one raises `ValueError`. Failures and timeouts are caught and logged. **Cancellation is passed on**, so the process can be killed. |
| `Scheduler(pm=None)` | Loads the config, runs the main loop, and supports adding and removing tasks at runtime. `pm` runs the `cmd` tasks; if it's missing, a `ProcessManager()` in the default directory is used. |
| `read_config(path, existing_names=)` | Parses a config file into loaded `ScheduledTask`s. Invalid entries, disabled tasks and duplicate names are logged and skipped. Used by `load_config()` and `reload_config()`. |
| `await Scheduler.reload_config(path)` | Replaces the task list with the file's tasks while the scheduler runs. New tasks and tasks whose interval changed are rescheduled, and other changes apply at the next run. Runs in progress continue, even for removed tasks. Returns the added, removed and updated names. |
| `Scheduler.run_now(name)` | Starts a run of the task right away, outside its schedule, and doesn't wait for it. Respects `allow_overlap`. Backs the `scheduler.run` RPC method. |
| `main()` | The `geenii-scheduler CONFIG` entry point: an alias that runs the geenii daemon with this scheduler config. |

Module constant: `RUNS_KEPT_PER_TASK` (10), the number of finished runs kept
per `cmd` task.

### Execution of `cmd` tasks

A `cmd` task runs as a **Process Manager process**: the scheduler decides
*when* to run it, and the Process Manager runs and records it. Inside the
daemon, `ProcessHost` passes its own `ProcessManager` to the scheduler
(`scheduler.pm`). A standalone `Scheduler()` creates one in the default
directory.

1. Each argument is expanded with `os.path.expandvars` (for example `$GEENII_BIN`).
2. `pm.start(argv, env=, cwd=working_dir, pid=<run ID>)` starts the command
   without a shell, in its own process group. The run ID is
   `<task>-<UTC YYYYmmddTHHMMSS>-<4 hex>`. The task name is sanitized for
   process IDs: characters other than `[A-Za-z0-9_-]` become `-`, and it is
   cut to 40 characters. The ID is stored as `task.last_run_id` and shown in
   `Scheduler.status`.
3. `await pm.wait(run_id)`. The output is written to the run's
   `stdout.log`/`stderr.log`, not to the scheduler log. Read it with
   `geenii pm output <run ID>`.
4. A non-zero exit becomes a `RuntimeError` naming the run ID, which `run()`
   catches and logs.
5. If the run is cancelled (by a timeout or by `stop()`), the process is
   killed with `pm.kill()`: `SIGTERM` to the **process group**, then `SIGKILL`
   if it is still running after `KILL_WAIT_S`. Child processes of the command
   are stopped too.
6. **Retention:** after each run, finished runs of the task beyond the newest
   `RUNS_KEPT_PER_TASK` (10) are deleted with `pm.cleanup()`. Runs are matched
   by the exact run-ID pattern, so a task named `tick` doesn't touch
   `tick-other`'s runs. Two task names that sanitize to the same string would
   share a retention window.

Because runs are ordinary processes, they appear in `geenii pm list`, and
`geenii pm kill <run ID>` stops one. A killed run counts as a failed run for
the scheduler.

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
- The scheduler has no process of its own. The daemon's `ProcessHost` starts
  it together with the other components and stops it first on shutdown.

`Scheduler.status` returns the following:

- for each task: its name and interval, next and last run times (ISO), and a
  `running` flag
- the number of running tasks
- the overall state, `running` or `stopped`

---

## Process Manager

`geenii/pm/` provides a way to run commands in the background. The commands
outlive the caller (the agent or CLI call that started them), and their output
is saved to files on disk. It runs inside the geenii daemon:

```
ProcessingAgent / geenii pm CLI
        │  ProcessManagerClient (a DaemonClient calling pm.*)
        ▼
  geenii daemon  →  ProcessHost  →  ProcessManager (asyncio; children write directly to the log files)
        │
  $GEENII_CACHE_DIR/processes/<pid>/{meta.json, stdout.log, stderr.log}
```

The daemon has to be running before the client can be used
(`geenii daemon start`).

`pm/process_manager_service.py` is kept for compatibility.
`ProcessManagerService(socket_path, pm=)` is a `DaemonServer` whose
`ProcessHost` uses the given `ProcessManager`, and the module's `main()` runs
the daemon.

### Commands: shell or no shell

The type of `cmd` decides how the command is executed:

| `cmd` type | Execution | Use for |
|---|---|---|
| `str` | Through the shell (`/bin/sh -c`, via `proc.shell_argv()`) | Command lines with pipes, redirects, `&&`, `cd`, `$VAR`. This is what the agent tool and `geenii pm start` send |
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

An asyncio-based manager. All public methods are coroutines and must run on
the event loop that owns the manager, which is the daemon's loop. Blocking disk work runs in `asyncio.to_thread`: reading logs, scanning
for finished processes, and `rmtree`. Each process gets a short ID: 12 hex
characters, or a caller-supplied `pid`. That ID is separate from the OS
`system_pid`.

The child's stdout and stderr are **connected directly to the log files**, not
to pipes. The operating system writes the output unchanged, so there are no
reader tasks and nothing gets decoded or re-encoded. `wait()` returns as soon
as the process exits, and output keeps being written even if the manager dies
unexpectedly.

Process IDs become directory names, so they are validated. An ID must be 1–64
characters long, may contain only letters, digits, `_` and `-`, and must start
with a letter or digit. Anything else, including `..` or path separators,
raises `ValueError`. Reusing an ID that exists in memory or on disk is
rejected as well. An empty `pid` means "auto-generate".

| Method | Behavior |
|---|---|
| `await start(cmd, env=, cwd=, pid=)` | Validates `cmd` and `pid`. Under a lock, so that concurrent starts can't claim the same ID, it creates the process directory, opens the log files, and calls `proc.spawn()`, which gives the command its own process group. If spawning fails (for example, `cwd` doesn't exist), the directory is removed again. Then it writes `meta.json`, starts a waiter task and returns `ProcessInfo` with state `running`. |
| `await status(pid)` | Answers from memory while the process runs, otherwise from `meta.json`. Raises `KeyError` if the ID is unknown. Never creates files. |
| `await output(pid, stream="stdout", tail=None)` | Returns the log contents, or only the last `tail` lines. Works while the process is still running. `stream` must be `stdout` or `stderr`. |
| `await wait(pid, timeout=None)` | Waits until the process has finished and returns its final `ProcessInfo`. Returns right away for finished or orphaned processes. On timeout it raises `asyncio.TimeoutError`; a timeout or cancelled wait doesn't affect the process. |
| `await kill(pid, force=False)` | Sends `SIGTERM` (or `SIGKILL` with `force`) to the **process group**, so child processes are signalled as well. Waits up to `KILL_WAIT_S` (5s) for the exit, so the returned state is normally already `killed`. |
| `await list(include_finished=False)` | Processes in memory, plus finished ones from disk if requested, newest first. Each ID appears only once. |
| `await cleanup(pid)` | Runs `rmtree` on the process directory. Refuses while the process is still tracked. |
| `await shutdown()` | Terminates all running processes at the same time with `proc.terminate()` (process group `SIGTERM`, then `SIGKILL` after `TERMINATE_GRACE_S`), waits for their waiter tasks and records their final state. Called by `ProcessHost.stop()` when the daemon shuts down. |

The waiter task sets the final state from the return code:

| Condition | State |
|---|---|
| exit code `0` | `completed` |
| killed by a signal (`< 0`), or non-zero after `kill()`/`shutdown()` | `killed` |
| any other non-zero exit | `failed` |

It then rewrites `meta.json` (atomically, via a temporary file and
`os.replace`) and removes the process from memory. `meta.json` stores only env
**keys**; env values stay in memory.

**Orphans.** `recover()` looks for `meta.json` files still in the `running`
(or `pending`) state. That only happens if the previous daemon was killed
without a clean shutdown. The daemon calls `recover()` once at startup,
before it accepts connections. It is deliberately not called in `__init__`:
short-lived instances in the same directory, such as a local
`geenii scheduler run`, must not touch the daemon's live records. Those processes are
marked `orphaned`, with an explanation in `error`: whether they are still
running is unknown. Because the output goes straight to the log files, any
output they produce is still captured. They are not
signalled, because their OS pid may have been reused by another process.

### RPC methods

The process manager's operations are the `pm.*` methods of the daemon (see
[Wire protocol](#wire-protocol)). When the daemon stops, `shutdown()`
terminates all running processes.

### Client (`process_manager_client.py`)

`ProcessManagerClient(socket_path=None)` is a `DaemonClient` with typed
wrappers for the `pm.*` methods. Like every `DaemonClient` it is stateless:
each call opens a new connection, sends one request, reads up to the first
newline, and closes the connection. If the response has `"ok": false`, the
client raises `RuntimeError(error)`. `is_available()` checks that the socket
file exists and that `ping` succeeds. The client has no socket timeout.

### Integration

- `ProcessManagerAgent` (`geenii/agents.py`) creates a client and registers the
  tools from `geenii/core/process_tools.py`: `bg_process_start`,
  `bg_process_status`, `bg_process_output`, `bg_process_kill` and
  `bg_process_list`.
  - `bg_process_start` sends the command as a string, so it runs through the
    shell.
  - If no `working_directory` is given, it defaults to `GEENII_WORKING_DIR`,
    the same directory the `bash` tool uses. Without this default, the command
    would run in the directory the daemon was started from.
  - Errors (for example an invalid ID) are returned to the model as
    `{"error": ...}`.
- `geenii pm` (`cli/pm_cli.py`) provides `ping`, `start`, `status`, `output`,
  `kill`, `list` and `cleanup`, plus `serve`, an alias for
  `geenii daemon start`. The socket path can be overridden with `--socket`,
  `GEENII_SOCKET` or `GEENII_PM_SOCKET`.

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
