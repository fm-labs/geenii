# g33n11

Hybrid AI platform for local and remote large language models (LLMs)

- Use remote and local large-language-models seamlessly.
- Build and run your own chat assistants, autonomous agents and AI workflows with ease.
- Supports models from Ollama, OpenAI, HuggingFace, Local LLMs and more.
- Rich toolset for assistants and agents supporting python functions and serverless functions
- Supports Model-Context-Protocol (MCP) server tools.
- User-friendly CLI and WebUI for managing models, agents, tools and skills.
- Self-hosted solution for privacy and control over your AI workloads.
- Upcoming support for Anthropic's AGENT and SKILL specification format for reusable agent components.


## Quick start with Geenii CLI

To get started with Geenii, you can use the command-line interface (CLI).

Here are some basic commands to help you get started:


```bash
# Ask a simple question
geenii agents ask "What is the capital of France?"

# Ask a different agent or model
geenii agents ask --model "openai:gpt-4o-mini" "What is the capital of France?"
geenii agents ask --name "my_custom_agent" --model "ollama:qwen3:8b" "What is the capital of France?"

# Create/Ask a specific agent
geenii agents create "weather" --tools "get_weather_forecast" --system "You are a helpful assistant that provides weather information based on the get_weather_forecast tool."
geenii agents ask --name "weather" "What is the weather like in New York?"

# Create/Ask a specific agent with a specific tool
geenii agents create "computer" --tools "bash,applescript" --system "You are a helpful assistant that can control the computer using AppleScript."
geenii agents ask --name "computer" --tools "applescript" "Open Safari and navigate to https://www.google.com"

# Create/Ask an agent to perform a task
geenii agents create "organizer" --skills "email,calendar" --system "You are an organizer assistant that can send emails to help manage my schedule."
geenii agents ask --name "organizer" "Send an email to John Doe with the subject 'Meeting Reminder' and the body 'Don't forget about our meeting tomorrow at 10am.'"

# Create/Ask the default agent with a specific skill
geenii agents create "math_agent" --skills "math" --system "You are a helpful assistant that can perform mathematical calculations."
geenii agents ask "Is 33311 a prime number?"

# Create/Ask agent with a specific tool and skill
geenii agents create "data_analysis" --tools "python" --skills "pandas" --system "You are a data analyst assistant that can analyze sales data and provide insights."
geenii agents ask --name "data_analysis" --input @data.csv "Analyze the sales data for the last quarter and provide insights."


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

