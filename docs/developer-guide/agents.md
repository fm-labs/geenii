# Agents — Internals

This document covers the agent runtime, task queue, HITL system, and
programmatic API. For defining and configuring agents, see the
[user guide](../user-guide/agents.md).

## Runtime model

Class hierarchy (`geenii/agent/`, `geenii/agents.py`):

- `BotInterface` — minimal interface: `process(message) -> Iterator[ModelMessage]`.
- `BaseAgent` — the engine. Owns the tool registry, skill registry, message
  history, HITL controller, and a FIFO task queue (`collections.deque`).
  Subclasses decide which tasks to enqueue per message by implementing
  `_handle_message()`.
- `Agent` — the standard implementation: handles `@agent`, `/command` and
  `:tool` macros, otherwise enqueues `FindBestSkillTask` then `LLMTask`.
- `RoutingAgent` — enqueues `FindBestAgentTask` to hand the conversation off to
  the best-fitting configured agent (not used by default).
- `ProcessManagerAgent` — an `Agent` that additionally registers the process
  manager tools.

Each agent instance has a `cwd` (constructor argument). `init_agent()` passes
the spec's `working_dir`; `init_agent_by_name(name, cwd=...)` overrides it.
When no `cwd` is given, the agent creates a temporary directory
(`geenii_agent_<name>_*`, via `tempfile.TemporaryDirectory`) that is removed
when the agent object is garbage-collected — so agents without a
`working_dir` (including the built-in `default` and `routing` agents, and
agents started by `geenii agent` or the chat server) no longer run tools in the
process's cwd. `HandoffTask` passes the current agent's `cwd` to the target
agent.

`ToolCallTask` calls `invoke_tool(tool, ..., cwd=agent.cwd,
caller_id="agent:<name>:<call_id>")` (see
[tools.md](tools.md#invocation-and-logging)), which passes it to the tool as
`ctx.cwd` (`ToolCallContext`): `ComputerTool` and `PythonCliTool` run their
subprocess there, and `read`/`write` resolve relative paths against it. Its `execute()` generator returns the `ToolCallResult`;
blocked and rejected calls return one with `is_error=True`, and an exception
becomes `ToolCallResult(text=str(e), structured_content={"error": ...},
is_error=True)`. The `ToolCallResultContent` sent back to the model carries
`structured_content` if present, otherwise `text`. `read` and `write` only
accept paths inside the agent's `cwd`, `GEENII_WORKING_DIR` or the user
settings' `allowed_dirs`; the spec's `allowed_dirs` and shell commands are not
checked yet.

The agent runtime is fully synchronous: `process()`, task `execute()` methods,
tool `invoke()` and HITL controllers are plain (blocking) functions/generators.
To run several agents concurrently, run each one in its own thread or process;
a single agent instance is not meant to be shared between concurrent callers.

The tool registry is populated by `init_agent()` (`geenii/agent/registry.py`)
before the agent is constructed, based on its spec:

- If the spec's `tools` list contains `read`, `write` or `bash`, all built-in
  tools are registered (`init_builtin_tools()`).
- If the spec lists `mcp_servers`, only the tools of those servers are
  registered (`init_mcp_server_tools(registry, set(mcp_servers))`).
- Each name in `skills` is loaded into the skill registry.

On the first `process()` call, `BaseAgent._initialize()` runs once (lazily, so
subclasses can finish their own `__init__` first). For `Agent` it only warns
about `allowed_tools` that are not registered; it no longer loads MCP tools
itself. Which tools the model may actually call is controlled by
`allowed_tools` (from the spec's `tools` list or the CLI `--tools` override).

## The task queue

A message is processed by draining the queue (`_process_queue`), bounded by
`BaseAgent.MAX_TASKS = 15` tasks per message; when the limit is reached the
remaining tasks are dropped and an error message is yielded. Tasks are
`BaseTask` subclasses whose `execute()` is a generator; yielded values are
either:

- `ModelMessage` — streamed to the caller (CLI prints them as they arrive), or
- another `BaseTask` — appended to the end of the queue.

Errors in a task are caught and surfaced as an assistant error message; the
remaining tasks still run.

## Built-in tasks (`geenii/agent/tasks.py`)

| Task | Purpose |
|---|---|
| `LLMTask` | The main completion. Builds the full system prompt, sends the request (with the last `MAX_MESSAGE_HISTORY = 30` history messages), then drives the tool-call loop: all tool calls in a response are executed via `ToolCallTask`, then the completion is re-generated with the results. This repeats until the model answers without tool calls, bounded by `MAX_TOOL_CALLS = 10` per response and `MAX_RECURSION = 10` re-generations. `max_tokens` is estimated per request as (system prompt + input characters) / 4 + 8192. |
| `ToolCallTask` | Executes one tool call: emits an approval-request message, asks the HITL controller, invokes the tool (passing skill env vars), and appends the result to history. |
| `FindBestSkillTask` | Activates one or more skills on `agent.active_skills`. Tries, in order: auto-select (single skill), pre-selection, deterministic trigger matching (keyword-based, no LLM call), and LLM fallback (JSON output, temperature 0.1). Also registers any executable scripts in activated skills' `scripts/` directories as namespaced tools (`{skill}__{script}`). |
| `FindBestAgentTask` | LLM call that picks the best agent from the global registry, then yields a `HandoffTask`; falls back to a plain `LLMTask` when nothing fits. |
| `HandoffTask` | Instantiates the target agent (sharing the HITL controller) and forwards the prompt to it, streaming its messages back. History transfer is not implemented yet. |
| `PlanTask` | Experimental: asks the model for a step-by-step plan (each step optionally tagged with a skill), then enqueues a `FindBestSkillTask` + `LLMTask` pair per step. Not part of the default pipeline. |
| `ToolFilterTask` | Experimental: LLM-based pre-selection of relevant tools. Not part of the default pipeline. |

## System prompt assembly

For each `LLMTask` the system prompt is a list of parts:

1. The agent's instructions (`system` field + markdown body), or the default
   tool-usage-focused prompt from `geenii/agent/base.py`.
2. Context info: conversation context ID and current datetime.
3. If a skill is selected: the skill's description and full `SKILL.md` body.

## Message history and memory

`BaseAgent.message_history` is the list of `ModelMessage`s (user, assistant,
tool-call, and tool-result messages) held by the agent's `ChatMemory`
(`agent.memory`). Requests include the last 30 entries.

`geenii/memory.py` provides the `ChatMemory` implementations; unless a `memory`
is passed to the agent, `GEENII_MEMORY_ENGINE` selects one, keyed by the agent
name and `context_id`:

| Engine | Class | Storage |
|---|---|---|
| `file` | `FileChatMemory` | JSONL file, appended per message and restored on start |
| `sqlite` | `SqliteChatMemory` | SQLite database; safe to use from multiple threads |
| anything else | `ShortTermChatMemory` | in-process only, lost when the process exits |

The `/clear` and `/compact` macros clear the memory or summarise it into a new
context (`MemoryCompactionTask`).

## Info commands

Read-only slash commands answer from the agent's own state without calling the
model (`geenii/agent/info_commands.py`, `InfoCommandTask`):

| Command | Shows |
|---|---|
| `/self` | Name, class, model, conversation ID, memory, approval controller, tool count, MCP servers, loaded skills, and the agent's in-memory usage counters (see [Usage](#usage)) |
| `/usage` | Calls and tokens per model in this conversation, summed from `$GEENII_CACHE_DIR/logs/ai-usage-*.log` over the conversation ID and its `-<n>` compaction successors, including skill selection and `/compact` calls. Handoffs are not counted; see [usage-tracking.md](usage-tracking.md) |
| `/models` | Models of the configured providers, grouped by provider, with the agent's model highlighted |
| `/tools` | Allowed tools with descriptions: built-in, MCP grouped by server, and configured tools that did not load |
| `/context` | Message count by role, system prompt size, a rough token estimate (4 characters per token), number of compactions |
| `/help` | All built-in commands and skills, plus the `@agent` and `:tool` prefixes |

The reply is a markdown assistant message that is **not** added to memory, so
it never reaches the model's context and is not part of the stored history.
To add a command, write a `report_<name>(agent, args) -> str` function and
register it in `INFO_COMMANDS`. `Agent.BUILTIN_COMMANDS` includes them, so they
appear in `GET /agents/{name}/commands`. A built-in command wins over a skill of
the same name; the route logs a warning for such skills.

## Usage

Every agent counts its own model calls: `agent.usage` (a `Usage`, summed with
`+`) and `agent.model_calls`.

- **How calls are counted:** all agent tasks make their model calls through
  `_complete()` in `agent/tasks.py`. It tags the call for the usage log and
  calls `agent.record_usage(response.usage)`. That covers turns, tool
  follow-ups, skill and agent selection, tool filtering and `/compact`.
- **What isn't counted:** failed calls raise before they are counted. Info
  commands make no model calls.
- **Handoffs:** a handoff (`@agent`) adds the sub-agent's totals with
  `record_usage(sub.usage, calls=sub.model_calls)`, so the parent's counters
  include it.
- **Lifetime:** the counters belong to the agent **instance**. They grow
  across turns and survive `/clear` and `/compact`, but they are not
  persisted. In the server, a chat session's agent is rebuilt with fresh
  counters after a restart or an LRU eviction.
- **Where they show:** `/self` and the `agent.init` log entry (`to_dict()`).
  For persistent per-conversation numbers, use `/usage`, which reads the
  usage log ([usage-tracking.md](usage-tracking.md)).

A new task that calls a model should use `_complete(self.agent, request,
task=…)` rather than calling `generate_chat_completion` directly. Otherwise
its calls are neither tagged nor counted.

## Human-in-the-loop (HITL)

Every tool call passes through the agent's `HumanInTheLoopController`
(`geenii/hitl.py`) before execution:

| Controller | Behavior |
|---|---|
| `NoHumanInTheLoopController` | Auto-approves everything (the default) |
| `CliHumanInTheLoopController` | Interactive y/n prompt in the terminal (`geenii/cli/cli_runner.py`; currently not enabled by default) |
| `FileTicketHumanInTheLoopController` | Writes a `<call_id>.json` ticket file and waits (up to a timeout) for a `.approved`/`.rejected` file to appear |
| `HttpPollHumanInTheLoopController` | POSTs the request to an approval endpoint and expects `{"approved": bool}` |
| `WebHumanInTheLoopController` | Blocks until a web client answers via `respond(call_id, choice)` (`allow`/`approve`/`yes` approve); rejects on `cancel()` or after a timeout. Used by the server's `/chats` API (see [server.md](server.md#agent-chat)) |

A rejected call produces a tool-result message containing an error instead of
executing the tool.

## Programmatic use

```python
from geenii.g import init_agent_by_name

agent = init_agent_by_name("my-agent")

for message in agent.process("What's the weather in Vienna?"):
    for part in message.content:
        print(part.type, part.to_text())
```

`process()` blocks while the model and tools run. From async code (e.g. a
FastAPI endpoint), run it in a worker thread — e.g. return a
`StreamingResponse` over the generator, which Starlette iterates in its
threadpool, or use `await asyncio.to_thread(lambda: list(agent.process(msg)))`.

The [server](server.md) does exactly this: `WebAgentRunner` runs each chat
turn in its own thread and streams the messages as NDJSON events. It also
lists agent specs (`GET /api/v1/agents/`) and each agent's slash commands
(`GET /api/v1/agents/{name}/commands`: the `Agent.BUILTIN_COMMANDS`, then one
per configured skill).

MCP tools are the one async dependency: `McpClient` exposes a sync API and runs
every call on a single shared background event loop
(`geenii/utils/async_bridge.py`), so its persistent connections stay valid no
matter which thread calls them.
