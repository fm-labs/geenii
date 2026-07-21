# Configuration

All user-facing configuration lives in a single directory, resolved at import
time by `geenii/config.py`:

1. `GEENII_WORKING_DIR` — the working directory (defaults to the current
   working directory).
2. `GEENII_DIR` — the config directory (defaults to `$GEENII_WORKING_DIR/.geenii`).
3. `$GEENII_DIR/.env` is loaded automatically via python-dotenv (with
   `override=True`), so API keys can be kept next to the rest of the config.

## The `.geenii/` directory

```
.geenii/
├── .env                # environment variables (API keys etc.), auto-loaded
├── geenii.json         # user settings
├── mcp.json            # MCP server definitions
├── scheduler.json      # scheduled tasks (read by geenii-scheduler)
├── agents/             # one <name>.md per agent (see agents.md)
│   └── my-agent.md
├── skills/             # one directory per skill (see skills.md)
│   └── my-skill/
│       ├── SKILL.md
│       └── scripts/
└── .cache/             # logs, model catalogs, SQLite caches (GEENII_CACHE_DIR)
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `GEENII_WORKING_DIR` | `os.getcwd()` | Base working directory |
| `GEENII_DIR` | `$GEENII_WORKING_DIR/.geenii` | Config directory |
| `GEENII_CACHE_DIR` | `$GEENII_DIR/.cache` | Cache and log directory |
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

At agent initialization every configured server is contacted and its tools are
registered under the name `mcp__<server>__<tool>` (results cached for 1 hour).
See [tools.md](../developer-guide/tools.md).

## `scheduler.json` — scheduled tasks

Read by the standalone `geenii-scheduler` process. See
[scheduler.md](scheduler.md) for the format and semantics.

## Logs

Everything under `$GEENII_CACHE_DIR/logs/`:

- `ai-YYYY-MM-DD.log` — JSONL of every chat completion request and response.
  Note this includes full prompts and tool results; treat as sensitive.
- `ai-usage-YYYY-MM.log` — JSONL per-call usage (provider, model, context id,
  token counts, durations).
- `tools.log`, `scheduler.log`, `supervisor.log` — rotating component logs.
