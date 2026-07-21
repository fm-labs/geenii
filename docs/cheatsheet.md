# Cheatsheet


## CLI

```text
$ geenii --help
Usage: geenii [OPTIONS] COMMAND [ARGS]...

Commands:
  agent      Run an agent with the given name and initial prompt.
  agents     Manage agents.
  info       Show application info and configuration.
  mcp        Manage MCP servers and tools.
  scheduler  Manage the scheduler.
  skills     Manage skills.
  tools      Manage and execute tools.
```

### `geenii agent` — Run an agent

Run an agent directly from the command line. Override the model, tools, skills, or instructions on the fly.

```text
Usage: geenii agent [OPTIONS] PROMPT

Options:
  -n, --name TEXT               Name of the agent to run.
  -s, --skills TEXT             Comma-separated list of skills to enable.
  -t, --tools TEXT              Comma-separated list of tools to enable.
  -m, --model TEXT              Override the model (e.g. openai:gpt-4o-mini).
  -mp, --model-parameters TEXT  Model parameters as a JSON string.
  -si, --system TEXT            Override system instructions.
  -di, --developer TEXT         Override developer instructions.
  -f, --output-format TEXT      Output format: text, json.
  -i, --interactive             Continue the conversation after the initial prompt.
  -cid, --conv-id TEXT          Continue a previous conversation.
```

```bash
# Ask a simple question
geenii agent "What is the capital of France?"

# Use a specific model
geenii agent --model "openai:gpt-4o-mini" "What is the capital of France?"
geenii agent --model "ollama:qwen3:8b" "What is the capital of France?"

# Enable tools and skills
geenii agent --tools "websearch" "Search the web for the latest news on climate change."
geenii agent --skills "math" --tools python "Is 33311 a prime number?"
geenii agent --tools "bash,applescript" --skills "macos" "Open Safari and navigate to https://www.google.com"
```

### `geenii agents` — Manage agents

Create and manage agent configurations with specific models, tools, skills and instructions.

```bash
# List all configured agents
geenii agents list

# Inspect an agent's configuration
geenii agents inspect "my_agent"

# Create a new agent and then run it
geenii agents create "organizer" --skills "email,calendar" \
  --system "You are an organizer assistant that can send emails to help manage my schedule."
geenii agent -n "organizer" "Send an email to John with the subject 'Meeting Reminder'."
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
geenii mcp server show "duckduckgo"

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

Schedule agents to run on a cron-based schedule. Tasks are defined in `.geenii/scheduler.json`.

```bash
geenii scheduler start
geenii scheduler stop
geenii scheduler status
```

### `geenii info` — Show application info

Display version, configuration paths, and provider status.

```bash
geenii info
```
