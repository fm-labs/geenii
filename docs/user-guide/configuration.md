# Configuration

Configuration lives in two `.geenii/` directories, resolved at import time by
`geenii/config.py`:

1. `GEENII_WORKING_DIR` — the working directory (defaults to the current
   working directory). Project configuration is read from
   `$GEENII_WORKING_DIR/.geenii`.
2. `~/.geenii` in your home directory holds user-wide configuration. There is
   no `GEENII_DIR` variable any more; the project config directory is always
   `$GEENII_WORKING_DIR/.geenii`.
3. Two `.env` files are loaded automatically via python-dotenv:
   - `$GEENII_WORKING_DIR/.geenii/.env`, for per-project settings
   - `~/.geenii/.env` in your home directory, for settings shared by all
     projects (e.g. API keys)

   They act as defaults and never replace a variable that is already set.
   When the same variable is set in more than one place, this order applies:

   1. the shell / process environment (e.g. `OLLAMA_HOST=… geenii …`,
      `docker run -e`, CI secrets)
   2. the project `.env`
   3. `~/.geenii/.env`

   Either file may be missing. To let a `.env` value take effect, `unset` any
   variable of the same name in your shell first.

   `GEENII_WORKING_DIR` is resolved *before* the `.env` files are loaded, so
   it has to be set in the shell, not in a `.env`.
   All other variables below can go in either file.

## The `.geenii/` directory

```
.geenii/
├── .env                # environment variables (API keys etc.), auto-loaded
├── geenii.json         # user settings
├── mcp.json            # MCP server definitions
├── scheduler.json      # scheduled tasks (read by the geenii daemon)
├── services.json       # supervised services (read by the geenii daemon)
├── agents/             # one <name>.md per agent (see agents.md)
│   └── my-agent.md
├── skills/             # one directory per skill (see skills.md)
│   └── my-skill/
│       ├── SKILL.md
│       └── scripts/
```

Which files are read from the project directory, from `~/.geenii`, or from
both is listed per feature: agents, skills, flows, apps and `mcp.json` are read
from both.

Logs, model catalogs and caches are not stored here. They go in
`GEENII_CACHE_DIR`, which defaults to `~/.cache/geenii` in your home
directory and is shared by all working directories. (The default used to be
`~/.geenii/.cache`; move that directory to keep existing logs, usage stats
and agent memory.) See
[Caching](../developer-guide/caching.md#cache-directory) for its contents.

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `GEENII_WORKING_DIR` | `os.getcwd()` | Base working directory |
| `GEENII_CACHE_DIR` | `~/.cache/geenii` | Cache and log directory (in the user's home, shared by all working directories) |
| `GEENII_CACHE_DISABLED` | `false` | Set `true` to disable the `@cached` function cache |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_API_KEY` | _(empty)_ | Bearer token for Ollama (needed for Ollama Cloud) |
| `OPENAI_API_KEY` | _(empty)_ | OpenAI API key; the OpenAI provider counts as "configured" only when set |
| `ANTHROPIC_API_KEY` | _(empty)_ | Reserved — the Anthropic provider is not implemented yet |
| `MONGODB_URI`, `MONGODB_DB_NAME` | _(empty)_, `geenii_brain0` | Optional MongoDB model store (`utils/mongodb.py`) |
| `REDIS_URI` | _(empty)_ | Optional Redis model store (`utils/redis.py`) |
| `GEENII_CHAT_DB_PATH` | `$GEENII_CACHE_DIR/chat.db` | SQLite DB for the chat server (server repo) |
| `DEV_MODE` | `0` | When `1`, `geenii info` includes the full process environment in its report |

Values are read once at import time; changing them requires restarting the process.

## Model defaults

Default models are currently constants in `geenii/config.py` (not
env-configurable):

| Constant | Value |
|---|---|
| `DEFAULT_COMPLETION_MODEL` | `ollama:qwen3:8b` |
| `DEFAULT_IMAGE_GENERATION_MODEL` | `openai:dall-e-2` |
| `DEFAULT_AUDIO_TRANSCRIPTION_MODEL` | `openai:whisper-1` |

Agents override the completion model per-agent via the `model` field in their
definition file; the CLI can override it per-run with `--model`.

## `geenii.json` — user settings

Read by `config.read_user_settings()`. Recognized keys and their defaults:

```json
{
  "theme": "system",
  "notifications": true,
  "language": "en-US",
  "environment": {},
  "skill_dirs": []
}
```

- **`skill_dirs`** — extra directories to search for skills, appended to the
  default skill search paths (see [skills.md](../developer-guide/skills.md)). This is the only
  key the core library consumes today.
- `theme`, `notifications`, `language`, `environment` are reserved for the
  UI/server. Example configs in the wild may contain additional keys
  (`providers`, `defaultProvider`, `skillRepositories`); these are currently
  ignored by the core library.

If the file is missing or malformed, defaults are used.

## `mcp.json` — MCP servers

Standard `mcpServers` map, passed to [fastmcp](https://github.com/jlowin/fastmcp)'s
`MCPConfig`. Both stdio (command) and HTTP (url) transports are supported:

```json
{
  "mcpServers": {
    "duckduckgo": {
      "type": "stdio",
      "command": "docker",
      "args": ["run", "--rm", "-i", "mcp/duckduckgo"],
      "environment": {}
    },
    "my_http_server": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

At agent initialization the servers listed in the agent's `mcp_servers` are
contacted and their tools are registered under the name
`mcp__<server>__<tool>` (results cached for 1 hour).
See [tools.md](../developer-guide/tools.md).

Geenii uses the current MCP protocol version by default. For a server that
only speaks an older protocol version, add `"legacy": true` to its entry:

```json
"old_server": { "command": "old-mcp-server", "legacy": true }
```

To keep secrets out of individual entries, put them in a top-level `env` map
and refer to them as `${NAME}` in `command`, `url`, `args`, and `env` or
`headers` values:

```json
{
  "env": { "API_TOKEN": "…" },
  "mcpServers": {
    "my_http_server": {
      "url": "http://localhost:8000/mcp",
      "headers": { "Authorization": "Bearer ${API_TOKEN}" }
    }
  }
}
```

The values are filled in when geenii connects to the server. A name with no
value is left as written. Values come only from this `env` map, not from your
shell environment.

You can also add, edit and delete servers in the web UI under
Console → Configure → MCP. Those changes are saved to `~/.geenii/mcp.json`;
servers defined in the project's `.geenii/mcp.json` can't be changed there.

## `scheduler.json` — scheduled tasks

Read by the geenii daemon at startup (`geenii daemon start`). See
[scheduler.md](scheduler.md) for the format and semantics.

## `services.json` — supervised services

Long-running processes that the geenii daemon starts at startup and restarts
when they exit. Manage the file with `geenii supervisor add/remove/list`; after
editing it by hand, run `geenii supervisor reload`. See the
[supervisor CLI reference](../cli-reference/supervisor.md#servicesjson) for
the format.

## Logs

Everything under `$GEENII_CACHE_DIR/logs/`:

- `ai-YYYY-MM-DD.log` — JSONL of every chat completion request and response.
  Note this includes full prompts and tool results; treat as sensitive.
- `ai-usage-YYYY-MM.log` — JSONL per-call usage (provider, model, context id,
  token counts, durations).
- `tool-use-YYYY-MM-DD.log` — JSONL of every tool call made by agents,
  `geenii tools call` and the server's tool endpoint: caller, tool, arguments,
  env (values of names containing `password`, `secret`, `api_key` or `token`,
  or with a `_`-separated part `pass`, `passwd` or `pat`, e.g. `GH_PAT`, are
  redacted), working directory and result. Treat as sensitive.
- `tools.log`, `scheduler.log`, `supervisor.log` — rotating component logs.
