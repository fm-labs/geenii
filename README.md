# g33n11

**g33n11** (pronounced "geenii") is a self-hosted, AI-as-a-service platform that allows you to run and manage 
large language models (LLMs) locally or remotely, build chat assistants, autonomous agents and AI workflows with ease.


## Key Features

- 🔗 Use remote and local large-language-models seamlessly.
- 🤖 Build and run your own chat assistants, autonomous agents and AI workflows with ease.
- 🧠 Supports models from Ollama, OpenAI, HuggingFace, Local LLMs and more.
- 🛠️ Rich toolset for assistants and agents supporting python functions and serverless functions
- 🔌 Supports Model-Context-Protocol (MCP) server tools.
- 🖥️ User-friendly CLI and WebUI for managing models, agents, tools and skills.
- 🔒 Self-hosted solution for privacy and control over your AI workloads.
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
Usage: geenii [OPTIONS] PROMPT

  Run an agent with the given name and initial prompt. Optionally override skills, tools, model, model parameters, system
  instructions, developer instructions, and output format.

Options:
  -n, --name TEXT               Name of the agent to run.
  -s, --skills TEXT             Comma-separated list of skills to enable for the agent.
  -t, --tools TEXT              Comma-separated list of tools to enable for the agent.
  -m, --model TEXT              Override the model specified in the agent config.
  -mp, --model-parameters TEXT  Override the model parameters specified in the agent config. Should be a JSON string.
  -si, --system TEXT            Override the system instructions specified in the agent config.
  -di, --developer TEXT         Override the developer instructions specified in the agent config.
  -f, --output-format TEXT      Output format for the responses. Options: text, json.
  -c, --continue                Continue the conversation after the initial prompt.
  --help                        Show this message and exit.
```

To manage agents, tools, MCP servers and skills, you can use the `geenii` CLI:

```text
$ geenii --help

Usage: geenii [OPTIONS] COMMAND [ARGS]...

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  agents  Manage agents.
  skills  Manage skills.
  tools   Manage and execute tools.
  mcp     Manage MCP servers.
  models  Manage models.
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
geenii agent --skills "math" "Is 33311 a prime number?"

# Use computer tools
geenii agent --tools "bash" "List all files in the current directory."
# Use compoter tools with a specific skill
geenii agent --tools "bash,applescript" --skill "macos" "Open Safari and navigate to https://www.google.com"
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

# MCP Tools
# Note: MCP (Model-Context-Protocol) tools are a special type of tool that can interact with language models in a more structured way. 
# Under the hood, MCP tools are registered as regular tools.

# List installed MCP servers
geenii mcp server list

# Add a new MCP server
geenii mcp server add "my_mcp_server" --url "http://localhost:8000"
geenii mcp server add "my_local_mcp_server_stdio" --command "docker run --rm my_mcp_stdio_server_image"

# Get information about a specific MCP server
geenii mcp server info "my_mcp_server"

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


## Geenii in a box Quick Start Guide

Run geenii in a docker container with the pre-installed skills and tools.

Simply put all the agents, skills, tools and plugins in the `.geenii` folder and mount it to the container. 
You can also mount a `data` folder to persist any data generated by the agents, tools or skills.

The typical folder structure would look like this:

```text
working-directory/
├── .geenii
│   ├── agents
│   │   └── email.md
│   ├── skills
│   │   └── my_skill
│   │       └── SKILL.md
│   ├── tools
│   │   └── my_tool.py
│   ├── geenii.json
│   └── mcp.json
├── data
│   └── (data generated by agents, tools or skills will be stored here)
```

```bash
# Pull the latest image
docker pull docker.io/fmlabs/geenii:latest
docker run -it --rm --name geenii fmlabs/geenii:latest

# Run the container without data persistence (any data generated by agents, tools or skills will be lost when the container is stopped)
cd working-directory
docker run -it --rm --name geenii -v $(pwd)/.geenii:/.geenii fmlabs/geenii:latest

# Run the container with data persistence
cd working-directory
docker run -it --rm --name geenii -v $(pwd)/data:/data -v $(pwd)/.geenii:/.geenii fmlabs/geenii:latest

# Run the container with data persistence and a specific workspace mount 
# e.g. if you want to run agents that need access to files in a specific directory, you can mount that directory to the container
# Add ":ro" at the end of the mount to make it read-only for the agents, tools and skills running in the container
cd working-directory
docker run -it --rm --name geenii -v ${HOME}/my-shared-agent-data:rw -v $(pwd)/data:/data -v $(pwd)/.geenii:/.geenii fmlabs/geenii:latest
```

**Tipp:** Create an alias in your shell configuration file (e.g. `.bashrc` or `.zshrc`) to easily run the container from anywhere in your terminal:

```bash
alias xgeenii='docker run -it --rm --name geenii -v $(pwd)/data:/data -v ${HOME}/.geenii:/.geenii fmlabs/geenii:latest geenii'
alias xgeenii-update='docker pull docker.io/fmlabs/geenii:latest'

# Now you can use containerized `geenii` and `geenii` commands directly in your terminal, and the data will be persisted in the `data` folder.
xgeenii-update
xgenii --help
xgeenii --help
```

Replace `$(pwd)` with `${HOME}` if you want to use a global `.geenii` folder in your home directory instead of the current working directory.

Optionally, you can also use a docker volume instead of a bind mount for the `data` folder to persist the data generated by agents, tools or skills:
    
```bash
# Create a docker volume for data persistence
docker volume create geenii_data
# Run the container with the docker volume
docker run -it --rm --name geenii -v geenii_data:/data -v $(pwd)/.geenii:/.geenii fmlabs/geenii:latest
```

**Full Example using a local model with Ollama and a custom agent with git skill:**
```bash
export OLLAMA_API_KEY="your-ollama-api-key"
docker run -it --rm --name geenii \
  -v ${HOME}/.geenii:/.geenii:ro \
  -v $(pwd)/data:/data:rw \
  -v $(pwd):/workspace:rw \
  -e GEENII_USER_DIR=/.geenii \
  -e GEENII_WORKSPACE=/workspace \
  -e OLLAMA_API_KEY=${OLLAMA_API_KEY:?Variable not set} \
  -e OLLAMA_HOST=host.docker.internal \
  --add-host=host.docker.internal:host-gateway \
  fmlabs/geenii:latest \
  geenii --model "ollama:qwen3:8b" "Who are you?"
```