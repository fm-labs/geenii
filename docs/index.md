# geenii documentation

Welcome to the *Geenii* platform.

A minimal, but powerful, orchestration framework for agentic applications.



## Quick start with Geenii CLI

To get started with Geenii, you can use the command-line interface (CLI).

Here are some basic commands to help you get started:


```bash
# Ask a simple question
geenii wizards ask "What is the capital of France?"

# Ask a specific wizard
geenii wizards ask --name "weather" "What is the weather like in New York?"

# Ask a specific wizard with a specific tool
geenii wizards ask --name "computer" --tools "applescript" "Open Safari and navigate to https://www.google.com"

# Tell an wizard to perform a task
geenii wizards ask --name "organizer" "Send an email to John Doe with the subject 'Meeting Reminder' and the body 'Don't forget about our meeting tomorrow at 10am.'"

# Ask the default wizard with a specific skill
geenii wizards ask --skills "math" "What is 2 + 2?"

# Use wizard with a specific tool and skill
geenii wizards ask --wizard "data_analysis" --tools "python" --skills "pandas" "Analyze the sales data for the last quarter and provide insights."


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
geenii skills install "https://github.com/geenii/geenii-skills/mac-skills"

```