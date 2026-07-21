# Agents

An agent is a named configuration — model, instructions, tools, skills — plus a
runtime that processes prompts through an internal task queue.

## Defining an agent

Agents are markdown files with YAML frontmatter in `$GEENII_DIR/agents/<name>.md`.
The frontmatter is validated against `AgentSpec` (`geenii/agent/registry.py`);
the markdown body is appended to the system instructions.

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

### `AgentSpec` fields

| Field | Type | Meaning |
|---|---|---|
| `name` | str, required | Agent name; must match how you address it (`-n <name>`) |
| `model` | str, required | Model ID as `provider:model` (see [providers.md](providers.md)) |
| `description` | str | Shown in listings; also used by `FindBestAgentTask` to route between agents |
| `label` | str | Display label |
| `system` | str | Base system prompt (the markdown body is appended to it) |
| `tools` | list[str] | Tool names the agent is allowed to call (see [tools.md](tools.md)) |
| `skills` | list[str] | Skill names to load into the agent's skill registry |
| `model_parameters` | dict | Reserved; not currently applied to requests |
| `mcp_servers` | list[str] | Reserved; currently all configured MCP servers are loaded regardless |

A built-in `default` agent (model = `DEFAULT_COMPLETION_MODEL`) always exists;
placing a `default.md` in the agents directory overrides it.

## Runtime model

Class hierarchy (`geenii/agent/`, `geenii/agents.py`):

- `BotInterface` — minimal interface: `prompt(message) -> AsyncGenerator[ModelMessage]`.
- `BaseAgent` — the engine. Owns the tool registry, skill registry, message
  history, HITL controller, and an asyncio task queue. Subclasses decide which
  tasks to enqueue per prompt by implementing `_handle_prompt()`.
- `Agent` — the standard implementation: enqueues `FindBestSkillTask` then `LLMTask`.
- `RoutingAgent` — enqueues `FindBestAgentTask` to hand the conversation off to
  the best-fitting configured agent (not used by default).

On the first prompt, `BaseAgent._initialize()` registers the built-in tools and
discovers all MCP server tools into the agent's tool registry. Which of those
the model may actually call is controlled by `allowed_tools` (from the spec's
`tools` list or the CLI `--tools` override).

### The task queue

A prompt is processed by draining the queue (`_process_queue`), bounded by
`BaseAgent.MAX_TASKS = 10` per prompt. Tasks are `BaseTask` subclasses whose
`execute()` is an async generator; yielded values are either:

- `ModelMessage` — streamed to the caller (CLI prints them as they arrive), or
- another `BaseTask` — re-enqueued for execution.

Errors in a task are caught and surfaced as an assistant error message.

### Built-in tasks (`geenii/agent/tasks.py`)

| Task | Purpose |
|---|---|
| `LLMTask` | The main completion. Builds the full system prompt, sends the request (with the last 10 history messages), then drives the tool-call loop: each tool call in the response is executed via `ToolCallTask` and the completion is re-generated with the result, bounded by `MAX_TOOL_CALLS = 5`. If any tools were called, a follow-up `LLMTask` is enqueued to produce the final answer. |
| `ToolCallTask` | Executes one tool call: emits an approval-request message, asks the HITL controller, invokes the tool (passing skill env vars), and appends the result to history. |
| `FindBestSkillTask` | LLM call (JSON output, temperature 0.1) that picks the best skill for the prompt from the agent's loaded skills; sets `agent.selected_skill`. Skipped when no skills are loaded; auto-selects when exactly one is loaded. |
| `FindBestAgentTask` | LLM call that picks the best agent from the global registry, then yields a `HandoffTask`; falls back to a plain `LLMTask` when nothing fits. |
| `HandoffTask` | Instantiates the target agent (sharing the HITL controller) and forwards the prompt to it, streaming its messages back. History transfer is not implemented yet. |
| `PlanTask` | Experimental: asks the model for a step-by-step plan (each step optionally tagged with a skill), then enqueues a `FindBestSkillTask` + `LLMTask` pair per step. Not part of the default pipeline. |
| `ToolFilterTask` | Experimental: LLM-based pre-selection of relevant tools. Not part of the default pipeline. |

### System prompt assembly

For each `LLMTask` the system prompt is a list of parts:

1. The agent's instructions (`system` field + markdown body), or the default
   tool-usage-focused prompt from `geenii/agent/base.py`.
2. Context info: conversation context ID and current datetime.
3. If a skill is selected: the skill's description and full `SKILL.md` body.

## Message history and memory

`BaseAgent.message_history` is an in-process list of `ModelMessage`s (user,
assistant, tool-call, and tool-result messages). Requests include the last 10
entries. History is not persisted between CLI runs.

`geenii/memory.py` provides a `ChatMemory` abstraction with `ShortTermChatMemory`
(in-memory) and `FileChatMemory` (JSONL append/restore) implementations. A
`memory` parameter exists on `BaseAgent`, but it is not yet used by the runtime —
persistent conversations (`--conv-id`) are not functional yet.

## Human-in-the-loop (HITL)

Every tool call passes through the agent's `HumanInTheLoopController`
(`geenii/hitl.py`) before execution:

| Controller | Behavior |
|---|---|
| `NoHumanInTheLoopController` | Auto-approves everything (the default) |
| `CliHumanInTheLoopController` | Interactive y/n prompt in the terminal (`geenii/cli/cli_runner.py`; currently not enabled by default) |
| `FileTicketHumanInTheLoopController` | Writes a `<call_id>.json` ticket file and waits (up to a timeout) for a `.approved`/`.rejected` file to appear |
| `HttpPollHumanInTheLoopController` | POSTs the request to an approval endpoint and expects `{"approved": bool}` |

A rejected call produces a tool-result message containing an error instead of
executing the tool.

## Programmatic use

```python
from geenii.g import init_agent_by_name

agent = init_agent_by_name("my-agent")

async for message in agent.prompt("What's the weather in Vienna?"):
    for part in message.content:
        print(part.type, part.to_text())
```
