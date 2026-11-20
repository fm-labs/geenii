# geenii agent

Run an agent with a prompt.

## Synopsis

```
geenii agent [OPTIONS] [PROMPT]
```

## Description

Runs a named agent with the given prompt. Responses are streamed as they are
produced: intermediate messages (skill selection, tool-call requests, tool
results) and the final assistant message are printed with their content-part
type prefixed.

The command also accepts input from stdin when the terminal is not interactive.
When no prompt is given and `--interactive` is set, the user is prompted for
input.

## Options

| Option | Short | Default | Description |
|---|---|---|---|
| `--name` | `-n` | `default` | Agent to run |
| `--model` | `-m` | | Override the agent's model (`provider:model`) |
| `--tools` | `-t` | | Comma-separated tool names to allow |
| `--skills` | `-s` | | Comma-separated skills to load |
| `--system` | `-si` | | Override the system instructions |
| `--developer` | `-di` | | Override the developer instructions |
| `--model-parameters` | `-mp` | | JSON string of model parameters |
| `--output-format` | `-f` | `text` | Output format: `text` or `json` |
| `--interactive` | `-i` | | Keep prompting after the first response (type `exit` to quit) |
| `--context` | `-c` | | Continue a previous conversation by context ID |
| `--resume` | `-r` | | Continue the agent's last conversation (ignored with `--context`) |

## Conversations

Each run gets a new context ID unless `--context` or `--resume` is given.
The context ID of the last run of each agent is saved in
`$GEENII_CACHE_DIR/agents/<name>/last_context_id`; `--resume` continues that
conversation. With `--interactive` and neither option, the command asks
whether to restore the last conversation (default: no). The messages of a
restored conversation are loaded from the agent's memory, which is kept in a
file per conversation by default (see
[memory](../developer-guide/memory.md)).

## Examples

```bash
# default agent, default model
geenii agent "What is the capital of France?"

# specific model
geenii agent -m "openai:gpt-4o-mini" "What is the capital of France?"

# tools + skill
geenii agent -t "bash" -s "macos" "List all files in my Downloads folder"

# a configured agent, interactively
geenii agent -n fm4-track-checker -i "What's playing right now?"

# pipe from stdin
echo "Summarize this" | geenii agent
```

## See Also

- [agents](agents.md) — list and inspect configured agents
