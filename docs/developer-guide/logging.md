# Logging

Geenii writes logs through two separate mechanisms:

1. **Python `logging`** — the usual `logger = logging.getLogger(__name__)`
   messages, configured once per process by `geenii.logs.init_logging()`.
   Goes to the console and to a rotating file per process.
2. **Structured JSONL logs** — append-only files written directly by a few
   helper functions (`_ai_log`, `_ai_usage_log`, `_log_tool_call`,
   `_agent_log`, `proc_events.record`). They bypass `logging` entirely, so log
   levels and `GEENII_LOGGING` have no effect on them.

On top of that, captured **process output** (stdout/stderr of child
processes and services) lives in its own files or in memory.

This page describes the current behaviour, including its quirks.

## Where everything goes

All paths are relative to `$GEENII_CACHE_DIR` (default `~/.cache/geenii`),
unless stated otherwise.

| File | Format | Written by | When | Rotation / retention |
|---|---|---|---|---|
| `logs/<log-name>.log` | text, `LOG_FORMAT1` | Python `logging` (root handlers) | every log record ≥ INFO in that process | `RotatingFileHandler`, 10 MB × 10 backups |
| `logs/ai-YYYY-MM-DD.log` | JSONL | `geenii.ai._ai_log` | every chat completion request/response, every failed completion, and every provider call of the OpenAI and Ollama providers | new file per local day; never deleted |
| `logs/ai-usage-YYYY-MM.log` | JSONL | `geenii.ai._ai_usage_log` | every chat/text completion, successful or failed | new file per UTC month; never deleted |
| `logs/tool-use-YYYY-MM-DD.log` | JSONL | `geenii.tools._log_tool_call` | every tool invocation through `geenii.tools` (agents, `geenii tools call`, the server's tool endpoint) | new file per local day; never deleted |
| `logs/<agent>-YYYY-MM-DD.log` | JSONL | `geenii.agent.base_agent._agent_log` | agent lifecycle events (see below) | new file per local day; never deleted |
| `logs/proc-events-YYYY-MM.log` | JSONL | `geenii.proc_events.record` | process runs and control actions of the process manager, scheduler and supervisor | new file per UTC month; files older than `GEENII_PROC_EVENTS_KEEP_MONTHS` (default 12) are pruned when the daemon starts |
| `logs/server.log` | raw console output | `geenii server start --detach` | stdout/stderr of a detached server | appended; never rotated |
| `processes/<run-id>/stdout.log`, `stderr.log` | raw output | process manager | output of every process it starts (incl. scheduler `cmd` tasks) | scheduler keeps the last `RUNS_KEPT_PER_TASK` (10) runs per task; others until `pm cleanup` / `pm gc` |
| *(memory)* supervisor `LogBus` | `LogEvent` | `geenii.supervisor` | service and `run()` job output | ring buffer of 400 lines per service; lost on daemon restart |
| `<OS app log dir>/server.log`, `daemon.log` | raw output | desktop app (Tauri, `src-tauri/src/server.rs`) | stdout/stderr of the server and daemon it spawns | appended; never rotated |

The OS app log dir for the desktop app is Tauri's `app_log_dir()` for the
identifier `io.geenii.desktop`, e.g. `~/Library/Logs/io.geenii.desktop/` on
macOS.

The `logs/` directory is created by `config` at startup and again by each
writer if it is missing.

## 1. Python logging (`geenii/logs.py`)

### Setup

`init_logging(log_name=None, force=False)` configures the **root** logger with
`logging.basicConfig`, at level `INFO`. The handlers depend on the
`GEENII_LOGGING` environment variable:

| `GEENII_LOGGING` | Handlers | Format |
|---|---|---|
| `plain` (default) | `StreamHandler` (stderr) + `RotatingFileHandler` at `logs/<log-name>.log` | `%(asctime)s [%(levelname)s] %(name)s: %(message)s` |
| `rich` | `RichHandler` only — **no log file** | `%(name)s: %(message)s` with Rich's time/level/path columns |

The file name is resolved by `resolve_log_name()`:
`GEENII_LOG_NAME` → `log_name` argument → `"geenii"`. The result is
sanitised to a plain basename (anything outside `[A-Za-z0-9_.-]` becomes `-`,
leading dots are stripped).

Without `force=True`, `init_logging` is a no-op once the root logger has
handlers (`basicConfig` semantics).

### Who calls it

| Entry point | Call | Resulting file |
|---|---|---|
| `geenii <subcommand> …` (`cli/main.py`) | `init_logging(f"geenii-{subcommand}", force=True)` | `geenii-agent.log`, `geenii-scheduler.log`, `geenii-server.log`, `geenii-daemon.log`, … |
| `geenii` without a subcommand | `init_logging(None, force=True)` | `geenii.log` |
| `geenii.server.server` module import | `init_logging("geenii-server")` | `geenii-server.log` — only takes effect when uvicorn imports the module in a fresh process (e.g. `--reload`); otherwise the CLI already configured logging |
| `geenii.daemon.server.main()` | `init_logging("geenii-daemon")` | `geenii-daemon.log` (no-op when started through the CLI) |
| `plugins/casinogpt/agents.py` | `init_logging()` at import | `geenii.log` |

Because the CLI picks the name from the subcommand, each CLI command family
has its own rotating file. Set `GEENII_LOG_NAME` to override it, e.g. in a
scheduled task's `env` to give one task its own log file.

### Levels

- Root level is always `INFO`; there is no environment variable for it.
- `geenii --log-level LEVEL …` sets the level of the `geenii` and `httpx`
  loggers only. Third-party loggers stay at `INFO`.
- `geenii server` health probes (`cli/server_cli.py::_is_healthy`) raise the
  `httpx` logger to `WARNING` to keep per-request lines out of CLI output.
- uvicorn (`geenii server start`) is run with `log_level="info"` and its
  default log config, which gives the `uvicorn.*` loggers their own stderr
  handlers. Their lines (incl. access logs) show on the console, and in
  `logs/server.log` for a detached server, but not in `geenii-server.log`.

### What gets logged here (notable cases)

Most modules log at `INFO`/`WARNING`/`ERROR` as you would expect. A few are
worth knowing because they are verbose or may contain sensitive data:

- **Tool calls** (`tools.py`): `INFO` before every invocation with args, env
  (redacted, see below) and cwd, and `INFO` with the **full result** after it;
  `ERROR` on failure.
- **Providers**: one `INFO` line per completion with model and options (e.g.
  `OLLAMA: Generating chat completion model=…`).
- **Supervisor**: every line of service output, and every supervisor-internal
  message, is also logged at `INFO` as `[<name>][<tag>] <msg>`
  (`supervisor._emit`). In the daemon this puts all service output into
  `geenii-daemon.log`.
- **Scheduler**: task start, completion, timeout (`ERROR`), failure
  (`exception`), and skipped/invalid config entries.
- **Write failures of the JSONL logs**: `proc_events` uses
  `logger.warning`; `_ai_log` and `_ai_usage_log` use `print()` instead of the
  logger.

## 2. Structured JSONL logs

All of these append one JSON object per line via `append_jsonl` (or a plain
`open(..., "a")` in `proc_events`). They are written regardless of the
logging configuration and are never rotated by size.

### AI request log — `ai-YYYY-MM-DD.log`

`geenii.ai._ai_log(what, data)` writes `{"<what>": <data>}`. Entries:

| Key | Written by | When |
|---|---|---|
| `completion.request` | `ai.generate_chat_completion` | before every chat completion |
| `completion.response` | `ai.generate_chat_completion` | after a successful chat completion |
| `completion.error` | `ai._log_failed_call` | failed chat or text completion (`model`, `context_id`, `error`) |
| `provider.completion` | OpenAI and Ollama providers | right before the API call: model, full input messages, tool definitions, options |

The file name uses **local** time. Entries contain full prompts, tool
results and model output: treat the file as sensitive. Text completions
(`generate_completion`) are not request/response-logged, only their errors.
`_ai_log` never raises.

### AI usage log — `ai-usage-YYYY-MM.log`

`geenii.ai._ai_usage_log` writes one line per chat or text completion,
including failed ones (with empty `usage` and `error` set). Fields:
`timestamp` (UTC ISO with offset), `provider`, `context_id`, `model`,
`source`, `task`, `usage`, `usage_version`, `error`. The month in the file name
is the UTC month of `timestamp`. Never raises.

Readers: `usage_stats.py` (aggregation, cached under the cache dir), the
agents' `/usage` command and `agent/info_commands.py`. See
[Usage Tracking](usage-tracking.md) for details.

### Tool-use log — `tool-use-YYYY-MM-DD.log`

`geenii.tools._log_tool_call` runs in the `finally` block of every tool
invocation, so it records successes and failures. Fields: `timestamp` (local,
no timezone), `caller_id`, `tool`, `args`, `env`, `cwd`, `result` (the
`ToolCallResult` as a dict, or `{"exception", "traceback"}`).

`env` is passed through `_redact_env_vars`: values of names containing
`password`, `secret`, `api_key` or `token`, or with a `_`-separated part
`pass`, `passwd` or `pat`, plus the tool's declared secret keys, are
redacted. `args` and `result` are **not** redacted.

Unlike the AI logs, this writer is not wrapped in `try`: a failure to write
the log raises from the `finally` block and replaces the tool's own result or
error.

### Agent event log — `<agent-name>-YYYY-MM-DD.log`

`geenii.agent.base_agent._agent_log` writes
`{"agent", "context_id", "event", "data", "timestamp"}` (`timestamp` is a Unix
float). Events:

| Event | When |
|---|---|
| `agent.init` | start of a run, with the agent's `to_dict()` |
| `agent.message` | the incoming user message |
| `agent.task` | each task taken from the queue |
| `agent.task_result` | each result a task yields |
| `agent.max_tasks` | the task limit was hit |
| `agent.request_tool_execution` | the agent asks to execute a tool |
| `agent.load_skill` / `agent.unload_skill` | skill (un)loaded |

The agent name is used unsanitised in the file name, in the same `logs/`
directory as everything else, so an agent named e.g. `tool-use` or `ai` writes
into (or next to) those daily files. Not wrapped in `try`.

### Process event log — `proc-events-YYYY-MM.log`

`geenii.proc_events.record` writes one line per process event for the
process manager (`pm`), the scheduler and the supervisor. The envelope is
documented in the module docstring: `ts` (UTC, ms), `component`, `event`,
`name`, `run_id`, `system_pid`, `trigger`, `actor`, `cmd`, plus `state`,
`exit_code`, `duration_ms`, `error` on end events. `None` fields are omitted.

- **Run events** (feed `proc_stats`): `start`, `exit`, `spawn_error`,
  `timeout`, `skipped`, `restart_scheduled`, `gave_up`.
- **Audit events** (control actions, dotted names): `service.*`, `task.*`,
  `config.reload`, `pm.kill`, `pm.cleanup`, `pm.gc`. Daemon RPC handlers write
  these via `daemon/host.py::_audit`.

`cmd` is redacted (`redact_cmd`): secret-looking `KEY=value` / `--key=value`
values, the argument after a secret-looking flag and `Bearer …` tokens are
masked; arguments are capped at 32, each at 200 characters. Environment
values are never written. Writes are serialised with a lock and never raise.

Readers: `proc_stats.py` (aggregates into `$GEENII_CACHE_DIR/stats`),
`/api/v1/stats` routes (recent events, `audit` filter, CSV export).

## 3. Process and service output

| Source | Where the output goes | How to read it |
|---|---|---|
| Process manager (`pm/process_manager.py`), incl. scheduler `cmd` tasks | `processes/<run-id>/stdout.log` and `stderr.log` | `geenii pm output <run-id> [--stream stderr]` |
| Supervisor services and apps | in-memory `LogBus` (400 lines) **and** the daemon's Python log | `geenii supervisor logs <name>`, `supervisor.logs` / `apps.logs` RPC, `/services/{name}/logs` (SSE stream available) |
| Detached server (`geenii server start --detach`) | `logs/server.log` (or `--log-file`), stdout + stderr merged | the path is printed on start and shown by `geenii server status` |
| Server/daemon started by the desktop app | `<app log dir>/server.log`, `daemon.log` | `server_log` / `daemon_log` Tauri commands (`ServiceLogView`) |

Supervisor output is not persisted to its own file: after a daemon restart
it is only available in `geenii-daemon.log` (if `GEENII_LOGGING=plain`).

## Adding logging

- Use `logger = logging.getLogger(__name__)`; do not call `basicConfig` or add
  handlers in library code. Entry points call `init_logging()`.
- Do not log secrets. Reuse `tools._redact_env_vars` for env dicts and
  `proc_events.redact_cmd` for commands.
- For a new structured log, follow `_ai_usage_log` / `proc_events.record`:
  JSONL in `GEENII_CACHE_DIR/logs`, UTC timestamps with offset, the period in
  the file name derived from the same timestamp, and never raise from the
  writer. Resolve the directory at call time so tests can redirect
  `GEENII_CACHE_DIR`.

## Known gaps

- Only `proc-events-*` files are pruned; the daily `ai-*`, `tool-use-*` and
  agent logs, the monthly usage logs, `server.log` and the desktop app logs
  grow without limit.
- Timestamps are inconsistent: local naive time (`tool-use`, `ai-` file
  names), Unix float (agent log), UTC with offset (usage, proc events).
- `_log_tool_call` and `_agent_log` can raise on write errors.
- `GEENII_LOGGING=rich` drops the rotating file entirely.
- There is no environment variable for the root log level.
