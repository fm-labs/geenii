# CLI Reference

The CLI is built with click. The command group is assembled in `src/cli.py`;
the console-script name in `pyproject.toml` is `geenii-cli` (docs and README
examples use `geenii` — the intended final name).

Run from source with:

```bash
uv run --directory src python -m cli --help   # or: uv run geenii-cli --help
```

The CLI operates on the `.geenii` directory resolved from the current working
directory (or `GEENII_DIR` / `GEENII_WORKING_DIR`, see
[configuration.md](configuration.md)).

## Command overview

```
geenii
├── info                      # version, providers, models, system report
├── agent PROMPT              # run an agent with a prompt
├── agents
│   ├── list                  # configured + loaded agents
│   └── inspect NAME          # full agent configuration
├── tools
│   ├── list                  # all registered tools (built-in + MCP)
│   ├── inspect NAME          # tool schema and description
│   └── call NAME -a k=v ...  # invoke a tool directly
├── skills
│   ├── list
│   ├── inspect NAME [-i]     # -i/--instructions prints the SKILL.md body
│   └── install NAME SOURCE   # SOURCE must be file:///path/to/skill
└── scheduler
    ├── start | stop | status # placeholders — not implemented yet
```

## `geenii agent` — run an agent

```
geenii agent [OPTIONS] PROMPT
```

| Option | Meaning |
|---|---|
| `-n, --name` | Agent to run (default: `default`) |
| `-m, --model` | Override the agent's model (`provider:model`) |
| `-t, --tools` | Comma-separated tool names to allow |
| `-s, --skills` | Comma-separated skills to load |
| `-si, --system` | Override the system instructions |
| `-i, --interactive` | Keep prompting after the first response (type `exit` to quit) |
| `-mp, --model-parameters` | JSON string of model parameters *(accepted but not yet applied to requests)* |
| `-di, --developer` | Developer instructions *(accepted but not yet applied)* |
| `-f, --output-format` | `text` or `json` *(accepted but not yet applied)* |
| `-cid, --conv-id` | Continue a conversation *(not implemented yet)* |

Examples:

```bash
# default agent, default model
geenii agent "What is the capital of France?"

# specific model
geenii agent -m "openai:gpt-4o-mini" "What is the capital of France?"

# tools + skill
geenii agent -t "execute_command" -s "macos" "List all files in my Downloads folder"

# a configured agent, interactively
geenii agent -n fm4-track-checker -i "What's playing right now?"
```

Responses are streamed as they are produced: intermediate messages (skill
selection, tool-call requests, tool results) and the final assistant message
are printed with their content-part type prefixed.

## Related entry points

- `geenii-scheduler <config.json>` — runs the cron scheduler as a standalone
  process (see [scheduler.md](scheduler.md)). The `geenii scheduler ...`
  subcommands do not control it yet.

## Not in this repo

The README also describes `geenii mcp ...` and `geenii models ...` command
groups, a REST daemon, and a web UI. These are not part of the current CLI;
MCP servers are managed by editing `mcp.json` directly (see
[configuration.md](configuration.md)).
