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
├── daemon
│   ├── start                     # run the daemon (process manager, scheduler, supervisor)
│   ├── status                    # daemon info and component summary
│   └── stop                      # shut the daemon down
├── flow
│   ├── run PATH                  # run a flow file (-i input, -v k=v, -w workers)
│   ├── validate PATH             # check a flow and print its execution order
│   ├── graph PATH [-o FILE]      # flow graph as Mermaid / DOT, or an svg/png/pdf image
│   └── processors                # list registered processor types
├── pm
│   ├── ping                      # check if the daemon is running
│   ├── serve                     # alias for `daemon start`
│   ├── start COMMAND             # start a background process
│   ├── status PROCESS_ID         # check process state
│   ├── output PROCESS_ID         # show captured output
│   ├── wait PROCESS_ID           # wait for a process to finish (exits with its code)
│   ├── kill PROCESS_ID           # kill a process
│   ├── list                      # list background processes
│   └── cleanup PROCESS_ID        # remove on-disk logs for a finished process
├── scheduler
│   ├── start                     # alias for `daemon start --scheduler-config`
│   ├── status                    # live task state (or the config file offline)
│   ├── list                      # list configured tasks
│   ├── add NAME CMD              # add a task to the config (reloads the daemon)
│   ├── remove NAME               # remove a task from the config (reloads the daemon)
│   ├── reload                    # make the daemon re-read its config
│   └── run NAME                  # run a task now (in the daemon, or --local)
└── supervisor
    ├── status                    # supervised processes and their state
    ├── start NAME CMD            # start and keep a process running (ad hoc)
    ├── stop NAME                 # stop a process and stop supervising it
    ├── restart NAME              # restart a process now
    ├── logs NAME                 # recent output of a process
    ├── list                      # services declared in services.json
    ├── add NAME CMD              # declare a service in services.json (reloads the daemon)
    ├── remove NAME               # remove a service from services.json (reloads the daemon)
    └── reload                    # make the daemon apply services.json
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
- [daemon](daemon.md) — run and control the geenii daemon
- [flow](flow.md) — run and inspect flows (step pipelines)
- [pm](pm.md) — manage background processes
- [scheduler](scheduler.md) — manage and run the task scheduler
- [supervisor](supervisor.md) — keep long-running processes up

## Related Entry Points

- `geenii-daemon [--socket PATH] [--scheduler-config PATH]` runs the daemon
  (see [daemon](daemon.md)).
- `geenii-scheduler <config.json>` is an alias for
  `geenii-daemon --scheduler-config <config.json>`.
