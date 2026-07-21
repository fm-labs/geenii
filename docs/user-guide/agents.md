# Agents

An agent is a named configuration — model, instructions, tools, skills — that
determines how Geenii handles a prompt.

## Defining an agent

Agents are markdown files with YAML frontmatter placed in
`$GEENII_DIR/agents/<name>.md`. The markdown body is appended to the system
instructions.

```markdown
---
name: fm4-track-checker
description: Get information about the current music track playing on FM4
model: ollama:qwen3:8b
skills:
  - fm4-skills
tools:
  - python
  - display_desktop_notification
---

# Usage instructions

1. Fetch data using the scripts provided by the 'fm4-skills' skill.
2. Extract artist and track name.
3. Notify the user with 'display_desktop_notification'.
```

## AgentSpec fields

| Field | Type | Meaning |
|---|---|---|
| `name` | str, required | Agent name; must match how you address it (`-n <name>`) |
| `model` | str, required | Model ID as `provider:model` (e.g. `ollama:qwen3:8b`, `openai:gpt-4o-mini`) |
| `description` | str | Shown in listings; also used for automatic agent routing |
| `label` | str | Display label |
| `system` | str | Base system prompt (the markdown body is appended to it) |
| `tools` | list[str] | Tool names the agent is allowed to call |
| `skills` | list[str] | Skill names to load into the agent |
| `model_parameters` | dict | Reserved; not currently applied to requests |
| `mcp_servers` | list[str] | Reserved; currently all configured MCP servers are loaded regardless |

A built-in `default` agent (using `DEFAULT_COMPLETION_MODEL`) always exists;
placing a `default.md` in the agents directory overrides it.

## Running an agent

```bash
# default agent
geenii agent "What is the capital of France?"

# named agent
geenii agent -n fm4-track-checker "What's playing right now?"

# override model and tools
geenii agent -m openai:gpt-4o-mini -t bash,python "List my Downloads"

# interactive mode
geenii agent -n my-agent -i "Hello"
```

See the [agent CLI reference](../cli-reference/agent.md) for all options.

## Listing and inspecting agents

```bash
geenii agents list
geenii agents inspect fm4-track-checker
```

See the [agents CLI reference](../cli-reference/agents.md) for details.
