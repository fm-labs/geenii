# Cheatsheet


## CLI

```text
$ geenii --help
Usage: geenii [OPTIONS] COMMAND [ARGS]...

Commands:
  agent       Run an agent with the given name and initial prompt.
  agents      Manage and run agents.
  apps        Manage GeeApps (micro applications), run by the geenii daemon.
  daemon      Run and control the geenii daemon (process manager, scheduler, supervisor).
  flow        Run and inspect flows (step pipelines).
  info        Show general information about Geenii.
  mcp         Manage MCP servers and tools.
  models
  pm          Manage background processes.
  projects    Manage projects.
  scheduler   Manage and run the task scheduler (it runs inside the geenii daemon).
  server      Start, stop and inspect the geenii HTTP server (API + web UI).
  skills      Manage skills.
  supervisor  Keep long-running processes up (runs inside the geenii daemon).
  tools       Manage and execute tools.
  worker      Run unattended agent instances and use agent mail and the blackboard.
```

### `geenii agent` — Run an agent

Run an agent directly from the command line. Override the model, tools, skills, or instructions on the fly.

```text
Usage: geenii agent [OPTIONS] [PROMPT]

Options:
  -n, --name TEXT               Name of the agent to run.
  -s, --skills TEXT             Comma-separated list of skills to enable for the agent.
  -t, --tools TEXT              Comma-separated list of tools to enable for the agent.
  -m, --model TEXT              Override the model specified in the agent config.
  -mp, --model-parameters TEXT  Override the model parameters specified in the agent config.
                                Should be a JSON string.
  -si, --system TEXT            Override the system instructions specified in the agent config.
  -di, --developer TEXT         Override the developer instructions specified in the agent config.
  -f, --output-format TEXT      Output format for the agent's responses. Options: text, json.
  -c, --context TEXT            Continue a previous conversation. Creates a new conversation if
                                omitted.
  -i, --interactive             Continue the conversation after the initial prompt.
  -r, --resume                  Resume the last conversation. Restores the memory
```

```bash
# Ask a simple question
geenii agent "What is the capital of France?"

# Use a specific model
geenii agent --model "openai:gpt-4o-mini" "What is the capital of France?"
geenii agent --model "ollama:qwen3:8b" "What is the capital of France?"

# Enable tools and skills
geenii agent --tools "web_fetch" "Summarize https://example.com"
geenii agent --skills "math" --tools python "Is 33311 a prime number?"
geenii agent --tools "bash" "Open Safari and navigate to https://www.google.com"

# Continue the last conversation, or a specific one
geenii agent -n my-agent -r "And what about Germany?"
geenii agent -n my-agent -c "<context id>" "And what about Germany?"
```

### `geenii agents` — Manage agents

Agents are markdown files in `.geenii/agents/` or `~/.geenii/agents/` (see the
[agents guide](user-guide/agents.md)); there is no command to create one.

```bash
# List all configured agents
geenii agents list

# Inspect an agent's configuration
geenii agents inspect "my_agent" --instructions

# Give an agent an environment variable and a secret (prompted for)
geenii agents env set organizer CALENDAR_ID=work
geenii agents env set organizer MAIL_TOKEN --secret
geenii agents env list organizer
```

### `geenii tools` — Manage and execute tools

Tools are registered callable functions that agents can use. They can be implemented in any programming language. MCP server tools are also registered as regular tools and configured via `.geenii/mcp.json`.

```bash
# List all registered tools (including MCP tools)
geenii tools list

# Inspect a specific tool
geenii tools inspect "my_tool"

# Call a tool directly
geenii tools call "my_tool" --args arg1=value1 arg2=value2
```

### `geenii mcp` — Manage MCP servers and tools

Manage MCP (Model Context Protocol) servers and their tools. Servers are configured in `.geenii/mcp.json`.

```bash
# List all configured MCP servers
geenii mcp server list

# Show a server's configuration
geenii mcp server inspect "duckduckgo"

# List tools provided by a server
geenii mcp server tools "duckduckgo"

# Execute a tool on a server
geenii mcp server tool_exec "duckduckgo" "search" -a query="python testcontainers"

# Execute a tool with JSON arguments
geenii mcp server tool_exec "duckduckgo" "search" -j '{"query": "python testcontainers", "max_results": 5}'
```

### `geenii skills` — Manage skills

Skills are reusable instruction packages, each represented as a directory containing a `SKILL.md` file.

```bash
# List installed skills
geenii skills list

# Inspect a skill
geenii skills inspect "my_skill"
geenii skills inspect "my_skill" --instructions

# Install a skill from a local directory
geenii skills install "my_skill" "file:///path/to/skills/my_skill"
```

### `geenii scheduler` — Manage the scheduler

Schedule agents to run on a cron-based schedule. Tasks are defined in `~/.geenii/scheduler.json`
and run inside the geenii daemon.

```bash
geenii daemon start          # runs the scheduler (and process manager, supervisor)
geenii scheduler status      # live state from the daemon
geenii scheduler run NAME    # run a task now
geenii daemon stop
```

### `geenii supervisor` — Keep processes running

Supervised processes run inside the daemon and are restarted when they exit.
Services added with `add` are saved in `~/.geenii/services.json` and start with the daemon.

```bash
geenii supervisor add web -- python -m http.server 8000     # persistent
geenii supervisor start tmp -- python -m http.server 9000   # ad hoc, until the daemon stops
geenii supervisor status
geenii supervisor logs web
geenii supervisor stop web
```

### `geenii worker` — Run agents unattended

A worker answers the mail of one agent. Tool calls are denied unless `--approve` allows them.
Mail, the blackboard and shared files are stored in `~/.geenii` (or `GEENII_HOME`).

```bash
geenii worker serve research --approve all     # run a worker (foreground)
geenii worker ask research "Any new papers?"   # mail it and wait for the reply
geenii worker send research "papers" "Any new papers?"
geenii worker inbox                            # your mail ('human')
geenii worker list                             # running workers
geenii worker post notes "Done for today."     # shared blackboard
geenii worker blackboard --topic notes
geenii worker send research "data" "Summarize this" -a ./data.csv   # attach a file
geenii worker files list research              # an agent's filebox
geenii worker files get f_3f9c…                # save a shared file
```

### `geenii info` — Show application info

Display version, configuration paths, and provider status.

```bash
geenii info
```
