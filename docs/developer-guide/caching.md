# Caching

Geenii caches in a few separate places. They do not share a common layer:
each has its own lifetime, its own scope, and its own way to clear it.

| Cache | Code | Scope | Lifetime | Cleared by |
|---|---|---|---|---|
| [Function cache](#1-function-cache-cached) | `utils/cached.py` | **all processes** (SQLite on disk) | TTL per function | TTL expiry, `GEENII_CACHE_DISABLED`, `--no-cache`, deleting `cache.sqlite` |
| [MCP clients](#2-mcp-client-cache) | `mcp_config.py` | process | until exit | `close_mcp_clients()` (atexit) |
| [MCP list results](#3-mcp-list-results) | `mcp_client.py` | one `McpClient` | client lifetime | never (no invalidation) |
| [Chat session runners](#4-chat-session-runners-lru) | `server/chat_sessions.py` | server process | LRU, 32 entries | eviction, session delete |
| [Skill instructions](#5-skill-instructions) | `skills.py` | one `SkillSpec` | object lifetime | never |
| [MCP config](#6-mcp-config) | `mcp_config.py` | process | until exit | `get_mcp_config(reload=True)` |
| [Prompt caching](#7-provider-prompt-caching) | `provider/anthropic/provider.py` | provider side | set by the provider (~5 min) | — |

Other files under the cache directory (logs, model catalog snapshots, agent
memory, process output) are covered in [Cache directory](#cache-directory).
They are stored state, not caches: nothing reads them back to skip work.

## 1. Function cache (`@cached`)

`geenii.utils.cached` is a memoizing decorator with a TTL and pluggable
storage. It works on sync and async functions.

```python
from geenii.utils.cached import cached

@cached(ttl=3600)                 # seconds; None = never expires
def enumerate_models() -> list[AIModelInfo]:
    ...

@cached(ttl=60, cachekey="fixed-key")                  # constant key
@cached(cachekey=lambda func, args, kwargs: args[0])   # custom key function
@cached(ttl=3600, cache_if=bool)                       # only store truthy results
```

`cache_if` is a predicate on the result. When it returns false, the result is
returned but not stored, so the next call runs the function again.

### Where it is used

| Function | TTL | Called by |
|---|---|---|
| `geenii.ai.enumerate_models()` | 1 h | `GET /ai/models` (`server/ai_routes.py`), `geenii models` CLI, the agents' models info command |
| `geenii.tools.read_mcp_server_tools(server_name, server_conf)` | 1 h, non-empty results only (`cache_if=bool`) | `init_mcp_server_tools()`: server startup, `geenii tools`, `geenii ai`, agents with `mcp_servers` |

`enumerate_providers()` has a commented-out `@cached` and is **not** cached.

### Keys

By default the key is the SHA-256 of
`json.dumps({"func": f"{func.__module__}.{func.__qualname__}", "args": args, "kwargs": kwargs}, sort_keys=True, default=str)`.

- For `read_mcp_server_tools` the server config is part of the key, so editing
  a server's entry in `mcp.json` (command, args, env, …) gives a fresh entry.
  Changing the server's code without changing its config does **not**.
- The function is identified by module and qualified name, so moving or
  renaming a cached function makes its old entries unreachable. They stay in
  the store until their TTL runs out.
- Arguments that are not JSON-serializable are turned into strings with `str()`.
  If an object's `str()` includes its memory address, the key changes every
  call and the cache never hits.

### Stores

`cache_store()` creates one store per process, on first use:

| Store | Used when | Persistence |
|---|---|---|
| `SqliteCacheStore` | default: `$GEENII_CACHE_DIR/cache.sqlite` | on disk, shared by all processes |
| `InMemoryCacheStore` | fallback if the SQLite store cannot be opened | process only |
| `FileCacheStore` | not used anywhere; one pickle file per key | on disk |

`SqliteCacheStore` stores values with `pickle` in a single table
`cache(key TEXT PRIMARY KEY, expiry REAL, value BLOB)`. It is set up for
several processes using it at once (CLI, server, and daemon at the same time):
WAL journal, `busy_timeout=5000`, `BEGIN IMMEDIATE` for writes, and up to three
retries with backoff when the database is locked or busy. Expired rows are
deleted when they are read. `purge_expired()` exists but nothing calls it.

Values must be picklable. A corrupt row or file is deleted and counts as a miss.

### Disabling

- `GEENII_CACHE_DISABLED=true` in the environment or `.env`
- `geenii --no-cache …` on the CLI (sets `config.CACHE_DISABLED` for that run)

Both skip reads **and** writes. The setting is checked on every call, so
changing it at runtime works. To clear everything, delete
`$GEENII_CACHE_DIR/cache.sqlite` (and the `-wal` / `-shm` files next to it).
There is no CLI command to clear it.

### Things to watch out for

- **`None` is never a hit.** A stored `None` looks the same as a miss, so a
  function that returns `None` runs every time.
- **Failure results are cached unless excluded.** A function that returns a
  fallback value on error (e.g. `[]`) caches that fallback for the full TTL.
  `read_mcp_server_tools` does this, so it uses `cache_if=bool`: an
  unreachable server, or one that has no tools, is asked again on the next
  call. Another option is to raise on error, since exceptions are never cached.
- **Model lists go stale.** A model you have just pulled into Ollama does not
  show up in `enumerate_models()` for up to an hour.
- The async wrapper calls the SQLite store directly on the event loop. Reads
  and writes are usually fast, but a locked database can block the loop for up
  to the busy timeout.

## 2. MCP client cache

`get_mcp_client_for_server(server_name)` in `mcp_config.py` keeps one
`McpClient` per server name in the module-level dict `_client_cache`. Every
`McpTool.invoke()` uses it, as do the `geenii mcp` CLI commands. The persistent
connection, and for stdio servers the subprocess, is therefore set up once per
process rather than once per tool call.

`close_mcp_clients()` closes them all and is registered with `atexit`. It is
registered after the async bridge's own hook, so it runs before the bridge loop
stops. Nothing evicts a client earlier. If an MCP server crashes, its cached
client stays in the dict until the process exits.

Tool **discovery** does not use this cache. `read_mcp_server_tools` opens a
short-lived `McpClient` and closes it once it has the tool list. Its result is
cached by `@cached` instead (see above).

## 3. MCP list results

Each `McpClient` keeps `_cache: dict[str, list]` keyed by kind (`tools`,
`resources`, `prompts`). The first `list_tools()` / `list_resources()` /
`list_prompts()` fetches from the server; later calls return the stored list.
The list is never refreshed, so a server that changes its tools at runtime is
not picked up while that client lives. For the clients in `_client_cache`, that
means until the process exits.

## 4. Chat session runners (LRU)

`ChatSessionStore` (`server/chat_sessions.py`) keeps one `WebAgentRunner` per
web-chat session, each with its own agent instance, memory and HITL controller.
They are held in an `OrderedDict` used as an LRU:

- `runner(context_id)` moves a hit to the end. On a miss it creates the agent
  and then calls `_evict()`.
- `_evict()` drops the least recently used runners while there are more than
  `max_runners` (default **32**). It **skips busy runners**, so a burst of
  concurrent chats can briefly push the count above the limit.
- Evicting a runner loses nothing: the session's memory is on disk
  (`<base_dir>/<context_id>/memory.jsonl`), and the agent is rebuilt on next
  use.
- Deleting a session cancels its runner and removes it.

## 5. Skill instructions

`SkillSpec.instructions` is a `functools.cached_property`. The `SKILL.md` body
is read on first access and kept for the life of that `SkillSpec`. Edits to
`SKILL.md` take effect only when the skill is loaded again (new process or new
registry).

## 6. MCP config

`get_mcp_config()` parses `mcp.json` once per process and keeps the result in
the module global `config`. Pass `reload=True` to read the file again. Note
that this does not touch the `@cached` tool listings or `_client_cache`.

## 7. Provider prompt caching

The Anthropic provider sends the system prompt as a list of text blocks and
marks the **first** block with `cache_control: {"type": "ephemeral"}`
(`_build_system_blocks`). Callers pass `request.system` as a list with the
stable part first:

- Agents: `[agent.system_prompt, context info (context id, current time), skill prompts…]`
  (`agent/tasks.py`, `_build_system_prompt`). Only the agent's own system
  prompt is cached. The context block contains the current time and so is
  different on every request.
- Tool / agent / skill selection tasks: `[SYSTEM_PROMPT, "Available …"]`.

The cache itself lives at Anthropic. Geenii only records what the provider
reports: `cache_read_input_tokens` and `cache_creation_input_tokens` in `Usage`.
OpenAI caches automatically and reports reads only. See
[Usage Tracking](usage-tracking.md) for how these counts are normalized and
shown by `/usage`.

## Cache directory

`GEENII_CACHE_DIR` (default `~/.geenii/.cache`) also holds files that are
stored state rather than caches:

| Path | Contents |
|---|---|
| `cache.sqlite` | the `@cached` store (section 1) |
| `logs/` | AI request log, usage log, agent and component logs |
| `ollama.models.json`, `openai.models.json` | snapshot of the last model listing; written, never read |
| `agents/<name>/memory.<context_id>.{jsonl,db}`, `agents/<name>/last_context_id` | agent memory |
| `processes/<pid>/` | process manager output (cleaned by its gc) |
| `sandboxes/<id>/Dockerfile` | generated sandbox images |
| `tts/` | HF text-to-speech output |
| `geenii.sock` | daemon socket (default path) |

Deleting the whole directory loses agent memory and logs, not just caches. To
reset only the caches, delete `cache.sqlite*`.
