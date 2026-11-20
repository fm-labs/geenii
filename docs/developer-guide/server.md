# HTTP Server

`geenii.server` is a FastAPI app that exposes agents, tools, AI completions,
agent chat sessions, apps and the [geenii daemon](processes.md#the-geenii-daemon-geeniidaemon)
(process manager, scheduler, supervisor) over HTTP. It is the backend of
the web UI ([web-ui.md](web-ui.md)) and also serves the built UI as static
files.

## Running

```bash
geenii server start [-d] [--reload]   # see ../cli-reference/server.md; stop with `geenii server stop`
uvicorn --app-dir ./src geenii.server.server:app --port 33311            # normal
uvicorn --app-dir ./src geenii.server.server:app --port 33311 --reload   # dev
python -m geenii.server.server     # honours GEENII_SERVER_HOST (127.0.0.1) and GEENII_SERVER_PORT (33311)
```

Interactive API docs are at `http://localhost:33311/docs` (OpenAPI at
`/openapi.json`).

## Module layout (`src/geenii/server/`)

| Module | Role |
|---|---|
| `server.py` | App setup: lifespan (registries), middleware, exception handlers, static web GUI mount |
| `router.py` | Mounts every route module under `API_ROUTE_PREFIX = "/api/v1"` |
| `public_routes.py` | `/health`, `/info` (no `dep_current_user`) |
| `agents_routes.py` | `/agents` — agent configs, their slash commands, writing spec files, and their environment (variables and secrets) |
| `tools_routes.py` | `/tools` — tool definitions and direct execution |
| `mcp_routes.py` | `/mcp` — configured MCP servers, their tools, and tool calls (see [mcp.md](mcp.md#http-api)) |
| `skills_routes.py` | `/skills` — skills in the app's `SkillRegistry` (`app.state.skill_registry`), read-only |
| `projects_routes.py` | `/projects` — projects configured in the user settings, read-only |
| `stats_routes.py` | `/stats` — AI usage statistics from the usage log, calculated in `geenii/usage_stats.py` |
| `ai_routes.py` | `/ai` — models, text/chat completion, image, speech, transcription |
| `chat_routes.py` | `/chats` — agent chat sessions with streamed turns and tool approvals |
| `chat_sessions.py` | `ChatSessionStore`: chat sessions on disk + per-session agent runners |
| `web_runner.py` | `WebAgentRunner`: runs one agent turn in a thread and turns it into stream events |
| `pm_routes.py` | `/pm` — proxy to the process manager daemon |
| `daemon_routes.py` | `/daemon` — whether the geenii daemon runs, and what it hosts |
| `scheduler_routes.py` | `/scheduler` — the scheduler config file with live task state, task editing, and manual runs |
| `supervisor_routes.py` | `/supervisor` — the services config file with live service state, service editing, start/stop/restart and logs |
| `daemon_helper.py` | Shared helpers for routes that use the geenii daemon (see [Daemon-backed routes](#daemon-backed-routes)) |
| `apps_routes.py` | `/apps` — GeeApps, through the daemon's `apps.*` methods (see [apps.md](apps.md#http-api)) |
| `security.py` | `dep_current_user` (stub, see [Security](#security)) |
| `flow_routes.py` | Placeholder, not mounted |

## Startup

The `lifespan` in `server.py` builds the shared state once per process:

| `app.state` | Built by | Contents |
|---|---|---|
| `agent_registry` | `init_global_agent_registry(projects=True)` | The built-in agents, all agent specs from `config.agent_paths()` (`$GEENII_WORKING_DIR/.geenii/agents/`, `~/.geenii/agents/`, `/var/geenii/agents/`, `/etc/geenii/agents/`), the agents added by [plugins](agents.md#plugins), plus `<project>/.geenii/agents/` of every project in the user settings (`config.project_paths()`); see [agents.md](agents.md#agent-registry) |
| `tool_registry` | `init_builtin_os_tools()`, `init_builtin_webtools()`, `McpToolLoader.attach()` | Built-in tools plus the tools of **all** servers in `mcp.json`. MCP servers are discovered in the background, so startup doesn't wait for them; their tools are added as each one becomes ready (see [mcp.md](mcp.md#background-loading)). Agents load their own MCP tools when they start, from the same loader |
| `chat_sessions` | `dep_chat_sessions` (lazily, on first `/chats` request) | `ChatSessionStore` over `GEENII_CHAT_SESSIONS_DIR` |

Route modules read this state through small `Depends()` helpers
(`dep_agent_registry`, `dep_tool_registry`, `dep_chat_sessions`).

## Endpoints

All paths are relative to `/api/v1`.

| Method & path | Returns |
|---|---|
| `GET /health` | `{"status": "ok"}` |
| `GET /info` | App info (`get_app_info()`); the UI polls this as its liveness check |
| `GET /agents/` | Bare array of agent specs (`name`, `label`, `description`, `model`, `system`, `tools`, `skills`, `mcp_servers`, `model_parameters`, `file_path`, `class_name`, `scope`, `working_dir`, `allowed_dirs`) |
| `GET /agents/{name}` | One agent spec plus `instructions` (the markdown body of its spec file). 404 for unknown agents |
| `GET /agents/{name}/commands` | `AgentCommand[]`: the built-in commands (`clear`, `compact` and the read-only info commands `self`, `usage`, `models`, `tools`, `context`, `help`; see [agents.md](agents.md#info-commands)) followed by one per configured skill. 404 for unknown agents |
| `POST /agents/` | Body `{spec, instructions, scope}`: `spec` is the frontmatter (`AgentSpecInput`: `AgentSpec` without `file_path`/`scope`), `instructions` the markdown body, `scope` `user` (default), `project` or `global`. Writes `<agent dir of scope>/<name>.md` and adds the agent to the registry. 201 with the agent like `GET /agents/{name}`; 400 invalid name, 409 name or file taken, 422 invalid spec |
| `PUT /agents/{name}` | Body `{spec, instructions}`. Replaces the agent's spec file and reloads it into the registry. A built-in agent (no `file_path`) gets a new file in the user agent directory. 400 when `spec.name` differs (no renames), 404 unknown, 409 if that user file already exists |
| `GET /tools/` | Bare array of tool definitions (`name`, `type`, `description`, `parameters` as JSON Schema) |
| `POST /tools/{name}/execute` | Body: the tool arguments as a JSON object. Returns a `ToolCallResult` (`text`, `structured_content`, `is_error`). The tool runs in `GEENII_WORKING_DIR`. The call is logged to the tool-use log with caller `web:tools`. 404 for unknown tools |
| `GET /mcp/servers` | Configured MCP servers (`env` values masked); `?reload=true` re-reads `mcp.json` |
| `POST /mcp/servers` | Body `{name, config}`. Adds the server to `~/.geenii/mcp.json`. 201, 400 invalid, 409 name taken |
| `GET /mcp/servers/{name}` | Server summary plus `server_capabilities`, `tools`, `resources`. Connects to the server. 404 unknown, 502 unreachable |
| `GET /mcp/servers/{name}/config` | Full `mcp.json` entry, `env` and `headers` values masked |
| `PUT /mcp/servers/{name}` | Body: the full entry; `********` keeps a stored value. Writes `~/.geenii/mcp.json`. 400, 404, 409 if only in the project file |
| `DELETE /mcp/servers/{name}` | Removes the server from `~/.geenii/mcp.json`. 204, 404, 409 if only in the project file |
| `POST /mcp/servers/{name}/tool/call` | Body `{tool_name, arguments}`. Raw MCP `CallToolResult`. 404 unknown server, 502 on failure |
| `GET /mcp/status` | Tool discovery status of every configured server (`pending`, `queued`, `loading`, `ready`, `failed`), with tool count and last error |
| `GET /mcp/servers/{name}/status` | The same for one server. 404 unknown |
| `POST /mcp/servers/{name}/reload` | Discovers the server's tools again in the background, bypassing the cache. 202 with its status, 404 unknown |
| `GET /skills/` | The skills in the registry, sorted by name: `name`, `path`, `source` (the skill path it was loaded from), `description`, `triggers`, `allowed_tools`, `metadata`, `scripts`, `used_by` (agents listing it). Skills whose SKILL.md can't be parsed are skipped at startup |
| `GET /skills/{name}` | The entry plus `instructions` (the markdown body of SKILL.md). 404 for unknown skills |
| `GET /projects/` | `ProjectInfo[]`: the projects from the user settings' `projects` key (`config.get_projects()`): `path` (resolved), `trusted` (`"trusted": true`), `exists` (the directory exists) |
| `GET /stats/usage` | Usage from `{GEENII_CACHE_DIR}/logs/ai-usage-*.log` over a range of local days: `?days=30` (default; `0` for all days with usage), or `start`/`end` (ISO dates, `end` defaults to today). Returns `totals`, `daily` (every day of the range, with `tokens_by_provider`), `hourly` (calls per hour of day), and `by_provider` / `by_model` / `by_source` / `by_task` sorted by tokens. Each log file's per-day aggregates are cached in memory and in `{GEENII_CACHE_DIR}/stats/`, keyed by the file's size and mtime; `?refresh=true` recalculates. 400 if `start` is after `end` |
| `GET /ai/models` | `AIModelInfo[]` |
| `POST /ai/completion` | One-shot text completion |
| `POST /ai/chat/completion` | Chat completion; history is kept per `context_id` |
| `POST /ai/image/generate`, `/ai/audio/speech` | Image and speech generation |
| `POST /ai/audio/transcribe` | Multipart upload (`input_blob`, max 25 MB, else 413) |
| `POST /ai/audio/translate` | 501, not implemented |
| `GET/POST /chats`, `GET/DELETE /chats/{id}` | Agent chat sessions; see [Agent chat](#agent-chat) |
| `GET/POST /chats/{id}/messages` | History; send a message and stream the turn |
| `POST /chats/{id}/interactions/{interaction_id}` | Answer a tool approval request |
| `POST /chats/{id}/cancel` | Cancel the running turn |
| `/chats/{id}/files…` | 501, not implemented |
| `/pm/…` | Process manager: `ping`, `processes` (list/start/get/output/wait/kill/delete), `gc` — see [processes.md](processes.md) |
| `/apps/…` | GeeApps: list, get, icon, start, stop, restart, logs, reload, add, enabled, autostart — see [apps.md](apps.md#http-api) |
| `GET /agents/{name}/env` | `AgentEnv {vars, secrets}`: the agent's variables and the **names** of its secrets (the HTTP side of [`geenii agents env`](../cli-reference/agents.md#env)). Changes apply to agent instances created afterwards. 404 unknown agent |
| `PUT /agents/{name}/env/vars` | Body: an object of strings. Replaces **all** variables of the agent. `AgentEnv`; 400 invalid variable name, 404 unknown agent |
| `PUT /agents/{name}/env/secrets/{key}` | Body `{"value": str}`. Creates or replaces one secret. `AgentEnv`; 400 invalid name, 404 unknown agent |
| `DELETE /agents/{name}/env/secrets/{key}` | Deletes one secret. `AgentEnv`; 404 unknown agent or secret |
| `GET /daemon/status` | `{running, socket, info, error}`. Always 200; `running` is false when the daemon socket can't be reached, `info` is the daemon's `info` result otherwise |
| `GET /scheduler/config` | `{path, exists, daemon: {running, config, status, error}, tasks, error}`. `path` is the config file the daemon uses, else `~/.geenii/scheduler.json`. `tasks` are the file's entries, disabled ones included, each with `live` (the running scheduler's state, or `null` if it hasn't loaded the task); tasks the daemon runs that aren't in the file are appended with `not_in_config: true`. A file that can't be read sets `error` |
| `POST /scheduler/tasks` | Body `TaskInput` (`name`, `interval`, `cmd` **or** `module`, `params`, `env`, `working_dir`, `timeout`, `allow_overlap`, `enabled`; see [scheduler.md](../user-guide/scheduler.md#task-configuration)). Appends the task to the config file. 201 with `{task, path, reload}`; 400 invalid, 409 name taken |
| `PUT /scheduler/tasks/{name}` | Body `TaskInput`; a different `name` renames the task. Keys the editor doesn't know are kept. `{task, path, reload}`; 404 unknown, 409 new name taken |
| `DELETE /scheduler/tasks/{name}` | Removes the task from the config file; a run in progress may finish. `{path, reload}`; 404 |
| `POST /scheduler/tasks/{name}/run` | Starts a run in the daemon now, outside the schedule. 202 `{name, status: "started", path}`; 409 when no daemon runs a scheduler, 404 task not loaded (disabled or invalid) |
| `GET /supervisor/config` | `{path, exists, daemon: {running, config, error}, services, error}`, like `/scheduler/config`, for `~/.geenii/services.json` (or the daemon's file). Each service has `live`; services the daemon supervises that aren't in the file (`geenii supervisor start`) are appended with `not_in_config: true` |
| `POST /supervisor/services` | Body `ServiceInput` (`name`, `cmd`, `restart`, `env`, `cwd`, `capture_output`, `max_failures`, `enabled`). Appends the service; a daemon that uses the file starts it. 201 with `{service, path, reload}`; 400 invalid, 409 name taken |
| `PUT /supervisor/services/{name}` | Body `ServiceInput`; a different `name` renames it. The daemon restarts the service. `{service, path, reload}`; 404, 409 |
| `DELETE /supervisor/services/{name}` | Removes the service; the daemon stops it. `{path, reload}`; 404 |
| `POST /supervisor/services/{name}/start`, `…/stop`, `…/restart` | `{name, status}` (`started`, `stopped`, `restarted`). Stop leaves the service listed as stopped until it is started or the daemon restarts; restart also resets the restart backoff. 404 not supervised, 409 no daemon |
| `GET /supervisor/services/{name}/logs?tail=200` | `{name, lines}`: stdout, stderr and supervisor events as `[tag] line` strings (`tail` 1–10000). 404 not supervised |

`POST /tools/{name}/execute` runs the tool with an empty env and **no HITL
approval** — it is an admin endpoint, so it can run arbitrary shell commands
through `bash` and `python`.

## Errors

Errors use real HTTP status codes and a `Problem` body
(`geenii.datamodels.Problem`):

```json
{"error": "Not Found", "status": 404, "detail": "Tool 'foo' not found."}
```

- **Expected errors:** raise `HTTPException(status_code, detail)`. The
  handler in `server.py` turns it into a Problem response. Document the
  status in the route's `responses={...}` so it shows up in OpenAPI.
  `ai_routes` uses 400 for invalid input, 502 when the provider fails and 501
  for missing features.
- **Unhandled exceptions** are caught by `unhandled_exception_middleware`
  and returned as **500** Problems.

This is a middleware on purpose. Starlette routes `@app.exception_handler(Exception)`
to the outermost `ServerErrorMiddleware`, which sits outside
`CORSMiddleware`, so those responses had no CORS headers and the browser
hid the error from the UI. Middlewares run in reverse order of addition, so
the catch-all middleware must stay **above** `app.add_middleware(CORSMiddleware, …)`
in `server.py`.

## Daemon-backed routes

The `daemon`, `scheduler`, `supervisor`, `apps` and `pm` routes talk to the
[geenii daemon](processes.md#the-geenii-daemon-geeniidaemon) through the
helpers in `daemon_helper.py`:

| Helper | Purpose |
|---|---|
| `dep_daemon_client()` | FastAPI dependency returning `DaemonClient(actor="api")`. Tests override it in `app.dependency_overrides` |
| `daemon_call(client, method, params, not_found=None)` | Calls a daemon method. 409 when the daemon isn't running, otherwise errors as below |
| `daemon_errors(not_found=None)` | Context manager with the same error mapping, for calls through other clients (`pm_routes` uses it with `ProcessManagerClient`) |
| `daemon_state(client, component)` | `(status, config path, error)` of the `scheduler` or `supervisor`; the status is `None` without a daemon |
| `config_path(client, component, default)` | `(path, live)`: the config file the daemon uses, else the default |
| `reload_config(client, component, live)` | Makes a daemon that uses the file reload it; returns `{reloaded, changes, error}` |

The scheduler and supervisor routes edit the config file directly (written
atomically, under a lock) and then call `reload_config()`, so they also work
without a daemon; the `reload` field of their responses says whether a
running daemon picked the change up. Only `run`, `start`, `stop`, `restart`
and `logs` need the daemon.

Daemon errors arrive as `"<ExceptionType>: <message>"` and are mapped to
`KeyError` 404, `ValueError` 400, `TimeoutError` 408 and any other exception
type 409, with the message as detail (`not_found` replaces it for a
`KeyError`). Errors without an exception type, such as `Unknown method: …`,
become 500, and connection errors 503.

## Agent chat

The `/chats` API powers the xchat UI. A session is an agent instance with its
own memory and HITL controller.

1. `POST /chats` with `{"agent": "default", "title": null}` returns
   `ChatSessionInfo {id, agent, title, created_at, updated_at}` (201).
2. `POST /chats/{id}/messages` with `{"prompt": "..."}` or
   `{"content": [ContentPart…]}` streams the turn as **NDJSON**
   (`application/x-ndjson`), one `ChatStreamEvent` per line:

   | `type` | Payload |
   |---|---|
   | `status` | `status`: `thinking`, `tool` or `awaiting_input` |
   | `message` | `message`: a `ChatMessage` envelope (`id`, `timestamp`, `sender_id`, `context_id`, `message: ModelMessage`) |
   | `error` | `error`: string; ends the turn |
   | `done` | Ends the turn |

   Only one turn runs per chat; a second request gets **409**. Text-only
   input is passed to the agent as a string, so `/command`, `@agent` and
   `:tool` macros work.
3. A tool call that needs approval arrives as a message with an
   `interaction` part, followed by `status: awaiting_input`. Answer it while
   the stream is open with `POST /chats/{id}/interactions/{interaction_id}`
   and `{"choice": "Allow"}`. `allow`, `approve` and `yes` (any case) approve;
   any other choice rejects. Unanswered requests are rejected after 300 s.
4. `POST /chats/{id}/cancel` rejects pending approvals and ends the turn at
   the next message. `DELETE /chats/{id}` cancels and deletes the session.

How it works:

- `WebAgentRunner.start()` runs `agent.process()` in its own thread and
  feeds a queue. The turn always runs to completion (or cancellation), even
  if the client disconnects, so a chat never stays busy.
- `WebHumanInTheLoopController` (`geenii/hitl.py`) blocks the tool call
  until `respond()` or `cancel()` is called.
- Sessions live in `~/.geenii/chats/<id>/` (`meta.json` + `memory.jsonl`,
  a `FileChatMemory`). Directories without `meta.json` belong to the
  `/ai/chat/completion` memory and are ignored. Session ids must match
  `[A-Za-z0-9_-]{1,64}`.
- Runners are kept in an LRU cache of 32. An evicted session is rebuilt from
  disk on its next request.

## Static web GUI

If `WWW_DIR` exists (`GEENII_WWW_DIR`, default `<repo>/www`), it is mounted at
`/` with `html=True`. It is mounted after the API routes, so `/api/v1/*`
always wins. Put the built UI (`geenii-ui/dist`) there to serve it from the
API server.

## Security

There is **no authentication** yet. `dep_current_user` is attached to every
router except `public_routes`, but it always returns
`User(username="user@localhost")`. The `_apptoken` the UI adds to app URLs
(see [apps.md](apps.md#ui)) is a fixed stub that nothing checks. CORS
allows all origins. Because `/tools/{name}/execute` and `/chats` can run
shell commands, bind the server to `127.0.0.1` (the default) and do not
expose it on a network.

## Adding a route module

1. Create `src/geenii/server/<name>_routes.py` with
   `router = APIRouter(prefix="/<name>", tags=["<name>"])`.
2. Read shared state through a `Depends()` helper on `request.app.state`, and
   initialise it in `lifespan` if it is new.
3. Use plain `def` handlers for blocking work (provider calls, agents, file
   I/O); FastAPI runs them in its threadpool. Use `async def` only for
   non-blocking code.
4. Raise `HTTPException` for client errors and list them in `responses=`
   with `{"model": Problem}`. For calls to the geenii daemon, use the
   helpers in `daemon_helper.py` (see [Daemon-backed routes](#daemon-backed-routes)).
5. Include it in `router.py` with `prefix=API_ROUTE_PREFIX` and
   `dependencies=[Security(dep_current_user)]`.
