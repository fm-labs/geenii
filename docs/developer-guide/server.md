# HTTP Server

`geenii.server` is a FastAPI app that exposes agents, tools, AI completions,
agent chat sessions and the process manager over HTTP. It is the backend of
the web UI ([web-ui.md](web-ui.md)) and also serves the built UI as static
files.

## Running

```bash
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
| `api_routes.py` | `/health`, `/info` |
| `agents_routes.py` | `/agents` — agent configs and their slash commands |
| `tools_routes.py` | `/tools` — tool definitions and direct execution |
| `ai_routes.py` | `/ai` — models, text/chat completion, image, speech, transcription |
| `chat_routes.py` | `/chats` — agent chat sessions with streamed turns and tool approvals |
| `chat_sessions.py` | `ChatSessionStore`: chat sessions on disk + per-session agent runners |
| `web_runner.py` | `WebAgentRunner`: runs one agent turn in a thread and turns it into stream events |
| `pm_routes.py` | `/pm` — proxy to the process manager daemon |
| `security.py` | `dep_current_user` (stub, see [Security](#security)) |
| `flow_routes.py` | Placeholder, not mounted |

## Startup

The `lifespan` in `server.py` builds the shared state once per process:

| `app.state` | Built by | Contents |
|---|---|---|
| `agent_registry` | `init_global_agent_registry()` | All agent specs from `$GEENII_DIR/agents/` |
| `tool_registry` | `init_builtin_tools()` | Built-in tools only. MCP server tools are not loaded here (`init_mcp_server_tools` is commented out); agents still load their own MCP tools when they start |
| `chat_sessions` | `dep_chat_sessions` (lazily, on first `/chats` request) | `ChatSessionStore` over `GEENII_CHAT_SESSIONS_DIR` |

Route modules read this state through small `Depends()` helpers
(`dep_agent_registry`, `dep_tool_registry`, `dep_chat_sessions`).

## Endpoints

All paths are relative to `/api/v1`.

| Method & path | Returns |
|---|---|
| `GET /health` | `{"status": "ok"}` |
| `GET /info` | App info (`get_app_info()`); the UI polls this as its liveness check |
| `GET /agents/` | Bare array of agent specs (`name`, `label`, `description`, `model`, `system`, `tools`, `skills`, `mcp_servers`, `model_parameters`, `file_path`, `class_name`) |
| `GET /agents/{name}` | One agent spec plus `instructions` (the markdown body of its spec file). 404 for unknown agents |
| `GET /agents/{name}/commands` | `AgentCommand[]`: the built-in commands (`clear`, `compact`) followed by one per configured skill. 404 for unknown agents |
| `GET /tools/` | Bare array of tool definitions (`name`, `type`, `description`, `parameters` as JSON Schema) |
| `POST /tools/{name}/execute` | Body: the tool arguments as a JSON object. Returns the tool output. 404 for unknown tools |
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
router except `api_routes`, but it always returns `User("test_user")`. CORS
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
   with `{"model": Problem}`.
5. Include it in `router.py` with `prefix=API_ROUTE_PREFIX` and
   `dependencies=[Security(dep_current_user)]`.
