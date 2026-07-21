# g33n11

**A versatile AI agent runner platform**

Opinionated abstraction layer for interaction with large language models, agents and tools.

## Main Components

- **CLI**: Command-line interface for managing models, agents, tools and skills.
  - **Agent Runner**: Run agents directly from the CLI with flexible options for overriding models, tools, skills and instructions.
  - **Agent Manager**: Create and manage agents with specific configurations for models, tools, skills and instructions.
  - **Tool Manager**: Register and manage tools that agents can use to perform specific tasks.
  - **MCP Server Manager**: Manage MCP servers that can be used as tools by agents to interact with language models in a more structured way.
  - **Skill Manager**: Install and manage skills, which are reusable components that can be used by agents to perform specific tasks.
  - **Scheduler**: Schedule and run agents on a cron-based schedule.


## Key Features

- 🔗 Use remote and local LLMs seamlessly.
- 🔒 Self-hosted solution for privacy and control over your AI workloads.
- 🤖 Build and run your own chat assistants, autonomous agents and AI workflows with ease.
- 🧠 **Multi-model** Supports models from Ollama, OpenAI, Anthropic and more.
- 🛠️ **Tool calling** Agents can call tools to perform specific tasks, and tools can be implemented in any programming language.
- 🔌 **Model-Context-Protocol** (MCP) server tools.
- 🧩 Support for Anthropic's AGENT and SKILL specification format for reusable agent components.


## Prerequisites

### AI Providers and Models

You can use local models with Ollama or remote models from OpenAI, Anthropic, OpenRouter and more.

**You will need at least one of the following AI provider configured to use Geenii** 

- An OpenAI API key to use OpenAI cloud models.
- Ollama API key to use Ollama's cloud models.
- Claude API key to use Anthropic cloud models.
- OpenRouter API key to use OpenRouter cloud models.


### Local Models (Optional but recommended)

**For local models, we recommend installing Ollama and using their local LLM support.**

- Ollama installed for local LLM support (optional but recommended). You can download it from [Ollama's official website](https://ollama.com/download).
- At least one local model installed. We recommend installing the Qwen3 series of models, which are high-performing local models that work well with Geenii. 


### Container Runtime (Optional)

**Unleash the full potential of Geenii by installing a container runtime to run agents, tools and additional services in isolated environments.**

- (Optional) Docker and Docker Compose installed on your machine. Easiest way is to install is downloading [Docker Desktop](https://www.docker.com/products/docker-desktop).
- (Optional) Podman installed on your machine. You can download it from [Podman's official website](https://podman.io/getting-started/installation). **Experimental!**


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


## Geenii in a Box

Run geenii in a Docker container with pre-installed skills and tools. See the [Docker guide](docs/docker.md) for setup instructions, data persistence, and examples.