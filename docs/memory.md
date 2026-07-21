# Agent Memory

Agent memory is the mechanism that gives an agent access to prior conversation
turns when generating its next response. Without memory every prompt is
stateless; with it the model can refer back to earlier exchanges.

## Data model

Every message — user, assistant, tool call, tool result — is represented as a
`ModelMessage` (defined in `geenii/datamodels.py`):

| Field | Type | Description |
|---|---|---|
| `type` | `str` | Always `"message"` |
| `role` | `str` | `"user"`, `"assistant"`, `"system"`, or `"tool"` |
| `content` | `list[ContentPart]` | One or more typed content parts (text, tool call, tool result, …) |
| `id` | `str` | Auto-generated UUID hex |
| `timestamp` | `datetime` | Auto-generated UTC timestamp |

`ContentPart` is a discriminated union defined in `geenii/chat_models.py`
covering text, images, audio, files, tool calls, tool results, JSON blobs,
and user-interaction payloads.

## Architecture

Memory is fully integrated into the agent loop. `BaseAgent` delegates all
message storage to a `ChatMemory` instance — there is no separate
`message_history` list. The property `agent.message_history` returns
`self.memory.messages`, and `add_to_history()` calls `self.memory.append()`.

### Automatic initialisation

When no `memory` argument is passed to the agent constructor, `__init_memory()`
selects a backend based on the `GEENII_MEMORY_ENGINE` config value
(from `geenii/config.py`):

| Engine value | Backend | Storage path |
|---|---|---|
| `"file"` (default) | `FileChatMemory` | `$CACHE_DIR/agents/<name>/memory.<context_id>.jsonl` |
| `"sqlite"` | `SqliteChatMemory` | `$CACHE_DIR/agents/<name>/memory.<context_id>.db` |
| anything else | `ShortTermChatMemory` | in-memory only, no persistence |

Each conversation gets its own file/database keyed by `context_id`, so
multiple concurrent sessions for the same agent don't collide.

You can also pass a pre-configured `ChatMemory` instance to the constructor
to override the automatic selection.

### How messages enter history

Inside `LLMTask` (`geenii/agent/tasks.py`):

1. The user prompt is wrapped in a `ModelMessage(role="user")` and added via
   `agent.add_to_history()` **before** the LLM call.
2. Each assistant response message is added **after** it is yielded.
3. For tool calls, the tool-call request (`role="assistant"`,
   content = `ToolCallContent`) is added **before** execution.

### Context window passed to the LLM

`LLMTask` slices the last N messages when building the completion request:

```python
MAX_MESSAGE_HISTORY = 20

input_messages = list(self.agent.message_history[-MAX_MESSAGE_HISTORY:])
```

After tool calls complete, the same slice is recomputed before requesting a
follow-up completion.

### Related limits

| Constant | Value | Location | Purpose |
|---|---|---|---|
| `MAX_MESSAGE_HISTORY` | 20 | `LLMTask` | Max messages sent as context |
| `MAX_TOOL_CALLS` | 10 | `LLMTask` | Max tool calls per single task |
| `MAX_RECURSION` | 10 | `LLMTask` | Max recursive tool-call rounds |
| `MAX_TASKS` | 15 | `BaseAgent` | Max tasks processed per prompt |

All constants are hardcoded; there is no user-facing configuration for them.

## ChatMemory abstraction

Defined in `geenii/memory.py`.

### Abstract base class — `ChatMemory`

```python
class ChatMemory(abc.ABC):
    _messages: list[ModelMessage]

    def append(message)   # adds to list + calls _insert()
    def clear()           # empties list + calls _write()
    def _insert(message)  # abstract — persist one message
    def _write()          # abstract — rewrite all messages
```

Supports `__iter__` and `__aiter__`.

### Backends

#### `ShortTermChatMemory`

In-memory only. `_insert()` and `_write()` are no-ops. Used when persistence
is not needed or `GEENII_MEMORY_ENGINE` is unset/unrecognised.

#### `FileChatMemory`

- Constructor: `FileChatMemory(file_path, create=True, restore=True)`
- On init (if `restore=True`): reads the JSONL file line-by-line, validates
  each line via `ModelMessage.model_validate()`.
- `_insert()`: opens the file in **append** mode and writes one JSON line.
- `_write()`: rewrites the entire file from the in-memory list.
- Tested in `tests/geenii/test_memory.py`.

#### `SqliteChatMemory`

- Constructor: `SqliteChatMemory(db_path)`
- Uses a `messages` table (`id` INTEGER PK, `role` TEXT, `content` TEXT as JSON).
- `_insert()`: inserts a single row.
- `_write()`: deletes all rows and re-inserts from the in-memory list.

## CLI chat memory

The CLI chat command (`geenii/cli/ai_cli.py`) uses its own ad-hoc
`List[ModelMessage]` that grows without limit for the duration of the CLI
session. It does not use `ChatMemory` or the agent memory system.

## Agent event logging (not memory)

`_agent_log()` in `base_agent.py` writes structured JSONL logs to
`$CACHE_DIR/logs/<agent>-<date>.log`. These capture events (prompts, task
executions, results) for observability but are not loaded back as
conversation context.

## Known gaps

1. **Tool results not always in history** — `ToolCallTask` has the
   `add_to_history()` call commented out for tool results.
2. **No token-aware truncation** — the hard cap of 20 messages ignores
   message size.
3. **No summarisation / compaction** — noted as a TODO in `tasks.py`.
4. **No cross-agent context transfer** — `HandoffTask` has a commented-out
   line for copying history to a sub-agent.
5. **Constants not configurable** — `MAX_MESSAGE_HISTORY` and related limits
   are hardcoded.
