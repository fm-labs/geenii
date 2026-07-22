# CLI Reference

The Geenii CLI is built with [click](https://click.palletsprojects.com/). The
main entry point is defined in `src/geenii/cli/main.py`; the console-script
name in `pyproject.toml` is `geenii`.

Run from source with:

```bash
uv run geenii --help
```

The CLI operates on the `.geenii` directory resolved from the current working
directory (or `GEENII_DIR` / `GEENII_WORKING_DIR`, see
[Configuration](../user-guide/configuration.md)).

## Global Options

| Option | Short | Description |
|---|---|---|
| `--version` | | Print the version and exit |
| `--no-cache` | | Disable caching |
| `--log-level` | | Set the logging level (`DEBUG`, `INFO`, `WARN`, `ERROR`, `CRITICAL`) |

## Command Tree

```
geenii
├── info                          # version, providers, system report
├── agent PROMPT                  # run an agent with a prompt
├── agents
│   ├── list                      # configured + loaded agents
│   └── inspect NAME              # full agent configuration
├── apps
│   ├── list                      # discovered apps with type
│   ├── info NAME                 # app details (type, status, port, path)
│   ├── start NAME [-p PORT]      # launch an app
│   ├── stop NAME                 # stop a running app
│   ├── init NAME [-t TYPE]       # generate manifest.json for one app
│   └── init-all                  # batch-generate manifests
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

## Subcommand Reference

- [agent](agent.md) — run an agent with a prompt
- [agents](agents.md) — list and inspect configured agents
- [apps](apps.md) — manage GeeApps (micro applications)
- [info](info.md) — show version and system information
- [models](models.md) — list available models
- [mcp](mcp.md) — manage MCP servers and tools
- [tools](tools.md) — list, inspect, and call tools
- [skills](skills.md) — list, inspect, and install skills
- [pm](pm.md) — manage background processes
- [scheduler](scheduler.md) — manage and run the task scheduler

## Related Entry Points

- `geenii-scheduler <config.json>` — runs the scheduler as a standalone
  process (see [scheduler](scheduler.md)).
