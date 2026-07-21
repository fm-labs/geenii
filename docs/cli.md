# CLI Reference

The CLI is built with click. The main entry point is defined in
`src/geenii/cli/main.py`; the console-script name in `pyproject.toml` is
`geenii`.

Run from source with:

```bash
uv run geenii --help
```

The CLI operates on the `.geenii` directory resolved from the current working
directory (or `GEENII_DIR` / `GEENII_WORKING_DIR`, see
[configuration.md](configuration.md)).

## Global options

| Option | Meaning |
|---|---|
| `--version` | Print the version and exit |
| `--no-cache` | Disable caching |
| `--log-level` | Set the logging level (`DEBUG`, `INFO`, `WARN`, `ERROR`, `CRITICAL`) |

## Command overview

```
geenii
├── info                          # version, providers, system report
├── agent PROMPT                  # run an agent with a prompt
├── agents
│   ├── list                      # configured + loaded agents
│   └── inspect NAME              # full agent configuration
├── models
│   └── list                      # available models (filterable)
├── mcp
│   └── server
│       ├── list                  # configured MCP servers
│       ├── show SERVER_ID        # server config as JSON
│       ├── tools SERVER_ID       # tools provided by a server
│       └── tool_exec SERVER_ID TOOL_NAME  # execute a tool on a server
├── tools
│   ├── list                      # all registered tools (built-in + MCP)
│   ├── inspect NAME              # tool schema and description
│   └── call NAME -a k=v ...      # invoke a tool directly
├── skills
│   ├── list
│   ├── inspect NAME [-i]         # -i/--instructions prints the SKILL.md body
│   └── install NAME SOURCE       # SOURCE must be file:///path/to/skill
├── pm
│   ├── ping                      # check if the process manager is running
│   ├── serve                     # start the process manager service
│   ├── start COMMAND             # start a background process
│   ├── status PROCESS_ID         # check process state
│   ├── output PROCESS_ID         # show captured output
│   ├── kill PROCESS_ID           # kill a process
│   ├── list                      # list background processes
│   └── cleanup PROCESS_ID        # remove on-disk logs for a finished process
└── scheduler
    ├── start                     # start the scheduler
    ├── status                    # show tasks and next run times
    ├── list                      # list configured tasks
    ├── add NAME CMD              # add a task to the config
    ├── remove NAME               # remove a task from the config
    └── run NAME                  # run a single task immediately
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
| `-di, --developer` | Override the developer instructions |
| `-mp, --model-parameters` | JSON string of model parameters |
| `-f, --output-format` | `text` or `json` |
| `-i, --interactive` | Keep prompting after the first response (type `exit` to quit) |
| `-cid, --conv-id` | Continue a conversation *(not implemented yet)* |

The command also accepts input from stdin when the terminal is not interactive.

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

## `geenii models` — list available models

```
geenii models list [OPTIONS]
```

| Option | Meaning |
|---|---|
| `-p, --provider` | Filter by provider name |
| `-l, --locality` | Filter by locality |

Outputs a table with name, provider, description, locality, and capabilities.

## `geenii mcp` — manage MCP servers

All MCP commands live under the `server` subgroup:

```bash
geenii mcp server list                          # list configured servers
geenii mcp server show <server_id>              # show server config as JSON
geenii mcp server tools <server_id>             # list tools from a server
geenii mcp server tool_exec <server_id> <tool>  # execute a tool
```

`tool_exec` accepts arguments via `-a key=value` (repeatable) or
`-j '{"key": "value"}'` for JSON input.

## `geenii pm` — process manager

The `pm` group manages background processes via a Unix-socket process manager
service.

```bash
geenii pm [--socket PATH] <command>
```

The `--socket` option (or `GEENII_PM_SOCKET` env var) sets the socket path for
all subcommands.

| Command | Description |
|---|---|
| `ping` | Check if the process manager service is running |
| `serve [--socket PATH]` | Start the process manager service |
| `start COMMAND [-d CWD] [-p PID]` | Start a background process |
| `status PROCESS_ID` | Check the state of a process |
| `output PROCESS_ID [--stream stdout\|stderr] [-n LINES]` | Show captured output |
| `kill PROCESS_ID [-f]` | Kill a process (`-f` sends SIGKILL) |
| `list [-a]` | List processes (`-a` includes finished) |
| `cleanup PROCESS_ID` | Remove on-disk logs for a finished process |

## `geenii scheduler` — task scheduler

The scheduler runs tasks on cron schedules or at fixed times.

```bash
geenii scheduler [command] [--config PATH]
```

All subcommands accept `--config` / `-c` to specify the scheduler config JSON
file (defaults to `.geenii/scheduler.json`).

| Command | Description |
|---|---|
| `start` | Start the scheduler and run tasks on their schedules |
| `status` | Show loaded tasks and their next run times (rich table) |
| `list` | List all configured tasks |
| `add NAME CMD --interval SPEC` | Add a task (`cron:EXPRESSION` or `at:DATETIME`) |
| `remove NAME` | Remove a task from the config |
| `run NAME` | Run a single task immediately, bypassing its schedule |

Examples:

```bash
geenii scheduler add cleanup echo cleanup --interval 'cron:0 * * * *'
geenii scheduler add oneshot echo done --interval 'at:2026-07-21T18:00:00Z'
geenii scheduler run cleanup
geenii scheduler list
```

The `add` command also supports `--env KEY=VALUE` (repeatable) and `--disabled`.

## Related entry points

- `geenii-scheduler <config.json>` — runs the scheduler as a standalone
  process (see [scheduler.md](scheduler.md)).
