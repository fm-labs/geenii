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


## Quick start with Geenii CLI

To get started with `geenii`, you can use the command-line interface (CLI).

```text
$ geenii --help

Usage: geenii [OPTIONS] COMMAND [ARGS]...

  Geenii CLI - A versatile command-line interface for AI agents, tools, and skills.

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  agent      Run an agent with the given name and initial prompt.
  agents     Manage agents.
  info       Show application info and configuration.
  scheduler  Manage the scheduler.
  skills     Manage skills.
  tools      Manage and execute tools.
```

Run an agent directly:

```text
$ geenii agent --help
Usage: geenii agent [OPTIONS] PROMPT

  Run an agent with the given name and initial prompt.
  Optionally override skills, tools, model, model parameters, system
  instructions, developer instructions, and output format.

Options:
  -n, --name TEXT               Name of the agent to run.
  -s, --skills TEXT             Comma-separated list of skills to enable for the agent.
  -t, --tools TEXT              Comma-separated list of tools to enable for the agent.
  -m, --model TEXT              Override the model specified in the agent config.
  -mp, --model-parameters TEXT  Override the model parameters. Should be a JSON string.
  -si, --system TEXT            Override the system instructions.
  -di, --developer TEXT         Override the developer instructions.
  -f, --output-format TEXT      Output format for the responses. Options: text, json.
  -i, --interactive             Continue the conversation after the initial prompt.
  -cid, --conv-id TEXT          Continue a previous conversation.
  --help                        Show this message and exit.
```


Here are some basic commands to help you get started:

```bash
# Ask a simple question
geenii agent "What is the capital of France?"

# Ask a different agent or model
geenii agent --model "openai:gpt-4o-mini" "What is the capital of France?"
geenii agent --model "ollama:qwen3:8b" "What is the capital of France?"

# Use a specific tool
geenii agent --tools "websearch" "Search the web for the latest news on climate change."

# Use a specific skill
geenii agent --skills "math" --tools execute_python "Is 33311 a prime number?"

# Use computer tools
geenii agent --tools "bash" "List all files in the current directory."
# Use computer tools with a specific skill
geenii agent --tools "bash,applescript" --skills "macos" "Open Safari and navigate to https://www.google.com"
```

Here are some basic commands to manage agents, tools, MCP servers and skills:

```bash
# Agents
# Create/Ask a specific agent to perform a task
geenii agents create "organizer" --skills "email,calendar" --system "You are an organizer assistant that can send emails to help manage my schedule."
geenii agent -n "organizer" "Send an email to John Doe with the subject 'Meeting Reminder' and the body 'Don't forget about our meeting tomorrow at 10am.'"

# Create/Ask the default agent with a specific skill
geenii agents create "math_agent" --skills "math" --system "You are a helpful assistant that can perform mathematical calculations."
geenii agent -n math_agent "Is 33311 a prime number?"

# Create/Ask agent with a specific tool and skill
geenii agents create "data_analysis" --tools "python" --skills "pandas" --system "You are a data analyst assistant that can analyze sales data and provide insights."
geenii agent -n "data_analysis" --input @data.csv "Analyze the sales data for the last quarter and provide insights."

# Tools
# Note: Tools are registered callable functions that an agent can use to perform specific tasks. 
# They can be implemented in any programming language and can be registered with Geenii.

# List installed tools
geenii tools list

# Get information about a specific tool
geenii tools inspect "my_tool"

# Call a tool directly from the CLI
geenii tools call "my_tool" --args arg1=value1 arg2=value2

# MCP Tools (planned)
# Note: MCP (Model-Context-Protocol) tools are a special type of tool that can interact with language models in a more structured way. 
# Under the hood, MCP tools are registered as regular tools.
# MCP servers are currently configured via the .geenii/mcp.json file.

# geenii mcp server list
# geenii mcp server add "my_mcp_server" --url "http://localhost:8000"
# geenii mcp server info "my_mcp_server"

# Skills
# Note: Skills are reusable components, represented as a directory containing a SKILL.md file

# List installed skills
geenii skills list

# Get information about a specific skill
geenii skills inspect "my_skill"

# Install a skill from a directory
geenii skills install "/path/to/skills/my_skill"

# Install a skill from a url (e.g. a folder in a GitHub repository)
# Only install from trusted sources!!
geenii skills install "https://github.com/geenii/geenii-skills/skills/mac-calendar"

```


## Geenii in a Box

Run geenii in a Docker container with pre-installed skills and tools. See the [Docker guide](docs/docker.md) for setup instructions, data persistence, and examples.