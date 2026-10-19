# Agents

An agent is a named configuration — model, instructions, tools, skills — that
determines how Geenii handles a prompt.

## Defining an agent

Agents are markdown files with YAML frontmatter named `<name>.md`. The
markdown body is appended to the system instructions. Agents are loaded from
these directories, and each one sets the agent's `scope`:

| Directory | Scope |
|---|---|
| `$GEENII_WORKING_DIR/.geenii/agents` | `project` |
| `~/.geenii/agents` | `user` |
| `/var/geenii/agents` | `global` |

`geenii agents list` and the HTTP server also load the agents of every
project registered in the user settings (`projects`, see
[configuration.md](configuration.md)) from `<project>/.geenii/agents`, with
scope `project`. A `project` agent's `working_dir` is set to its project
directory (the directory containing `.geenii/agents`), overriding a value in
the frontmatter.

If two directories define the same agent name, which one wins is currently not
defined (the directories are iterated as a set).

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
| `tools` | list[str] | Tool names the agent is allowed to call. Listing `read`, `write` or `bash` loads the built-in tools |
| `skills` | list[str] | Skill names to load into the agent |
| `model_parameters` | dict | Reserved; not currently applied to requests |
| `scope` | `builtin` \| `global` \| `project` \| `user` | Set from the directory the file was loaded from (see above); a value in the frontmatter is overwritten. The built-in agents are `global` |
| `working_dir` | str | Directory the agent's tools (`bash`, `python`, `read`, `write`) run in; `read`/`write` may access files inside it. Set automatically for `project` agents (see above). Without it, each agent instance gets a fresh, empty temporary directory that is deleted when the agent goes away |
| `allowed_dirs` | list[str] | Intended extra allowed directories for `project` agents. Stored and shown, not yet enforced |
| `mcp_servers` | list[str] | Names of MCP servers (from `mcp.json`) whose tools are loaded; servers not listed are not loaded. Their tools (`mcp__<server>__<tool>`) must still be listed in `tools` to be callable |

Built-in agents always exist: `default` and `routing` (both using
`DEFAULT_COMPLETION_MODEL`), `chatgpt` (`openai:gpt-3.5-turbo`) and `claude`
(`anthropic:claude-opus-4-6`). A file with the same name in an agents
directory overrides it.

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
