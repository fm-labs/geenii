# Messages & Content Parts

This document describes Geenii's internal message and content-part models, and
how each AI provider maps them to and from its wire format.

## Content parts (`geenii/chat_models.py`)

Every message carries a list of `ContentPart` objects. The `type` field is the
discriminator.

| Type               | Class                     | Key fields                                                        | Purpose                                                         |
|--------------------|---------------------------|-------------------------------------------------------------------|-----------------------------------------------------------------|
| `text`             | `TextContent`             | `text`                                                            | Plain text                                                      |
| `json`             | `JsonContent`             | `data` (dict/list)                                                | Structured data (promoted from text by optimistic JSON parsing) |
| `image`            | `ImageContent`            | `url`, `base64`, `alt`                                            | Image attachment                                                |
| `audio`            | `AudioContent`            | `url`, `duration`                                                 | Audio attachment                                                |
| `file`             | `FileContent`             | `url`, `filename`, `content_type`, `size`                         | File attachment                                                 |
| `embed`            | `EmbedContent`            | `title`, `description`, `url`, `thumbnail_url`, `video_url`       | Rich embed                                                      |
| `tool_call`        | `ToolCallContent`         | `name`, `arguments`, `call_id`, `require_approval`, `approval_id` | Model requests a tool invocation                                |
| `tool_call_result` | `ToolCallResultContent`   | `call_id`, `name`, `arguments`, `result`, `error`                 | Result returned to the model after tool execution               |
| `function`         | `FunctionCallContent`     | `name`, `arguments`, `result`                                     | Legacy function call (not used by the agent runtime)            |
| `confirmation`     | `UserConfirmationContent` | `confirmation_id`, `text`, `confirmed`                            | HITL approval request/response                                  |
| `interaction`      | `UserInteractionContent`  | `interaction_id`, `interaction_type`, `text`, `choices`, `choice` | Generic user interaction                                        |
| `widget`           | `WidgetContent`           | `name` (dot-notation, e.g. `geenii.clock`), `data`, `title`, `text` | UI widget; the UI renders it if known, else shows `text` (fallback); `title` is a small header above either |

The union type `ContentPart` is a Pydantic discriminated union over the `type`
field. Every content part has a `.to_text()` method for serialization.

### Built-in widgets

The UI ships these widgets, one file each in `geenii-ui/src/components/xchat/parts/widgets/`;
more can be registered via `<ChatProvider widgets={…}>`. Unknown widgets show `text`.

| Name              | `data`                                                                  |
|-------------------|-------------------------------------------------------------------------|
| `geenii.clock`    | `{ timezone?, label? }`                                                 |
| `geenii.table`    | `{ columns?, rows }`, rows are arrays or objects                        |
| `geenii.list`     | `{ items, ordered? }`, items are strings or `{ text, description? }`    |
| `geenii.barchart` | `{ title?, unit?, max?, items: [{ label, value }] }`                    |
| `geenii.html`     | `{ html, height?, title? }`, rendered in a sandboxed iframe              |
| `geenii.iframe`   | `{ url, scripts? = false, trusted? = false, height? = 320, title? }`, http(s) only; untrusted pages load on click; sandboxed, scripts only with `scripts`; "Open" button opens the url in a new window |
| `geenii.progress` | `{ label?, value?, max? = 100, status? }`, no `value`: indeterminate; `status`: `running`, `done`, `error` |
| `geenii.keyvalue` | `{ title?, items: [{ key, value }] }` or a plain object                 |
| `geenii.stat`     | `{ items: [{ label, value, unit?, delta? }] }`, `delta` in percent      |
| `geenii.code`     | `{ code, language?, filename? }`, with a copy button, no highlighting   |
| `geenii.countdown`| `{ until, label? }`, `until` is an ISO datetime                         |
| `geenii.json`     | `{ value, title?, expand? = 2 }`, collapsible tree; `expand`: levels opened initially |
| `geenii.csv`      | `{ csv, delimiter?, header? = true, title? }`, rendered as a table; delimiter detected if omitted |
| `geenii.steps`    | `{ title?, steps: [{ text, status? = pending, detail? }] }`; `status`: `pending`, `running`, `done`, `failed`, `skipped` |
| `geenii.diff`     | `{ diff, filename? }`, `diff` is unified diff text, computed by the sender |
| `geenii.linechart`| `{ title?, unit?, series: [{ name, points: [{ x, y }] }] }`, `x` is a number or an ISO date |
| `geenii.timeline` | `{ title?, items: [{ time, title, description?, level? = info }] }`, `time` is an ISO datetime |
| `geenii.filetree` | `{ root?, entries: [{ path, size?, type? }], expand? = 2 }`, `/`-separated paths; folders are created from the paths |
| `geenii.matrix`   | `{ text?, height? = 160, seconds? }`, digital rain; `text` fades in; stops after `seconds` (default: never) |
| `geenii.terminal` | `{ lines?, prompt? = 'C:\>', speed? = 30 }`, retro terminal that types `lines` (default: a boot sequence) |
| `geenii.snake`    | `{ size? = 16, speed? = 120 }`, playable Snake: focus it, arrows/WASD, space to start/pause |
| `geenii.fortune`  | `{ fortune?, width? = 40 }`, cowsay fortune; random if `fortune` is omitted |
| `geenii.dice`     | `{ count? = 1, values? }`, rolling dice (max 10); `values` are pre-rolled results |

## ModelMessage (`geenii/datamodels.py`)

```python
class ModelMessage:
    type: str = "message"
    role: str          # "user", "assistant", "system"
    content: list[ContentPart]
    id: str            # auto-generated UUID
    timestamp: datetime
    usage: Usage | None = None   # usage of the model call that produced it
```

This is the canonical message format used throughout the agent runtime: in
`BaseAgent.message_history`, yielded from tasks, and passed into
`ChatCompletionRequest.messages`.

`usage` is set on the **first** message created from each completion
response, and only there. A response with two tool calls becomes two
tool-call messages, and only the first carries the response's usage. So
summing `usage` over a conversation's messages counts every model call once.
User, tool-result and generated messages (errors, approval requests) have
`None`.

Messages with `usage` are:
- the final answer of an `LLMTask`, and the first tool-call message of each tool-calling response (stored in history only, not streamed);
- the `/compact` handover summary;
- the assistant messages of `/ai/chat/completion`.

`usage` is stored with the message by every `ChatMemory` and sent to `/chats`
clients in the stream. Providers ignore it when they build the history for
the model. See [usage-tracking.md](usage-tracking.md#the-usage-model) for the
fields.

## Request/response models (`geenii/datamodels.py`)

### ChatCompletionRequest

| Field              | Type               | Description                                                     |
|--------------------|--------------------|-----------------------------------------------------------------|
| `prompt`           | str                | The user's current prompt                                       |
| `model`            | str                | Model ID as `provider:model`                                    |
| `system`           | list[str]          | System prompt parts                                             |
| `messages`         | list[ModelMessage] | Conversation history                                            |
| `tools`            | set[str]           | Tool names the model may call                                   |
| `output_format`    | str                | `"json"`, `"auto"`, or None                                     |
| `output_schema`    | dict               | JSON schema for structured output                               |
| `model_parameters` | dict               | Provider-specific overrides (`temperature`, `max_tokens`, etc.) |
| `context_id`       | str                | Conversation context identifier                                 |
| `temperature`      | float              | Sampling temperature                                            |
| `top_p`            | float              | Nucleus sampling                                                |
| `max_tokens`       | int                | Max tokens to generate                                          |

### ChatCompletionResponse

| Field              | Type              | Description                               |
|--------------------|-------------------|-------------------------------------------|
| `output`           | list[ContentPart] | Parsed response parts                     |
| `output_text`      | str               | Aggregated text output                    |
| `reasoning_output` | str               | Thinking/reasoning content (if available) |
| `usage`            | Usage \| None     | Token counts, cache parts and timing      |
| `model_result`     | dict              | Raw provider response                     |
| `context_id`       | str               | Conversation context identifier           |

## Provider mappings

Each provider converts between `ModelMessage`/`ContentPart` and its native wire
format. The tables below show how each content part type maps.

### Ollama

Message history is converted by `model_messages_to_ollama_format()`.

| ContentPart             | Ollama wire format                                                                                |
|-------------------------|---------------------------------------------------------------------------------------------------|
| `TextContent`           | `{"role": <role>, "content": <text>}`                                                             |
| `JsonContent`           | `{"role": <role>, "content": json.dumps(data)}`                                                   |
| `ToolCallContent`       | `{"role": "tool", "tool_calls": [{"function": {"name": ..., "arguments": ...}}], "content": ...}` |
| `ToolCallResultContent` | `{"role": "tool", "content": "Tool call result: ..."}`                                            |
| Other types             | `{"role": <role>, "content": "[<type>] <to_text()>"}`                                             |

**System prompt:** Each part becomes a separate `{"role": "system", "content": ...}` message at the start.

**Tool definitions:** Generic tool defs are wrapped in `{"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}`.

**Response parsing:**
- `message.content` → `TextContent` (or `JsonContent` if optimistic JSON parsing succeeds)
- `message.tool_calls[].function` → `ToolCallContent` (call_id is generated as `xcall_<uuid>`)
- `message.thinking` → captured in `reasoning_output` but not emitted as a content part
- Usage: `prompt_eval_count` → `input_tokens`, `eval_count` → `output_tokens`, durations converted from nanoseconds to milliseconds

### OpenAI

Uses the OpenAI Responses API (`client.responses.create`).

| ContentPart             | OpenAI wire format                                                                     |
|-------------------------|----------------------------------------------------------------------------------------|
| `TextContent`           | `{"role": <role>, "content": <text>}`                                                  |
| `JsonContent`           | `{"role": <role>, "content": json.dumps(data)}`                                        |
| `ToolCallContent`       | `{"type": "function_call", "call_id": ..., "name": ..., "arguments": json.dumps(...)}` |
| `ToolCallResultContent` | `{"type": "function_call_output", "call_id": ..., "output": <result>}`                 |

If a `ToolCallResultContent` appears without a preceding `ToolCallContent` for
the same `call_id`, a placeholder `function_call` entry is injected to satisfy
the API.

**System prompt:** Joined into a single string and passed as `instructions`.

**Tool definitions:** Tools use their native `.to_openai()` format: `{"type": "function", "name": ..., "description": ..., "parameters": ...}`.

**Output format:**
- `output_schema` → `{"type": "json_schema", "schema": ..., "name": "OutputSchema"}`
- `output_format == "json"` → `{"type": "json_object"}`
- Otherwise → `{"type": "text"}`

**Response parsing:**
- `output[].type == "message"` → content items of type `output_text` become `TextContent` (with optimistic JSON parsing), `refusal` becomes a text part
- `output[].type == "function_call"` → `ToolCallContent` (call_id from the API, arguments JSON-decoded)
- Usage: directly from `model_result.usage`

### Anthropic

Uses the Messages API (`client.messages.create`).

| ContentPart             | Anthropic wire format                                                                                      |
|-------------------------|------------------------------------------------------------------------------------------------------------|
| `TextContent`           | `{"role": <role>, "content": <text>}`                                                                      |
| `JsonContent`           | `{"role": <role>, "content": json.dumps(data)}`                                                            |
| `ToolCallContent`       | `{"role": "assistant", "content": [{"type": "tool_use", "id": <call_id>, "name": ..., "input": ...}]}`     |
| `ToolCallResultContent` | `{"role": "user", "content": [{"type": "tool_result", "tool_use_id": <call_id>, "content": str(result)}]}` |
| Other types             | `{"role": <role>, "content": <to_text()>}`                                                                 |

System-role messages in history are **skipped** (system prompt is passed separately).

**System prompt:** Each part becomes a `{"type": "text", "text": ...}` block.
The first block gets `"cache_control": {"type": "ephemeral"}` for prompt
caching.

**Tool definitions:** Generic defs are mapped via `_to_anthropic_tool()`: `parameters` → `input_schema`.

**Output format:**
- `output_schema` → `output_config = {"format": {"schema": ..., "type": "json_schema"}}`
- `output_format == "json"` → a generic object schema is generated and passed as `json_schema`

**Response parsing:**
- `block.type == "text"` → `TextContent` (or `JsonContent` via optimistic parsing)
- `block.type == "tool_use"` → `ToolCallContent` (call_id from `block.id`)
- Usage: `input_tokens`, `output_tokens`, plus `cache_creation_input_tokens` and `cache_read_input_tokens`

## Optimistic JSON parsing

All three providers share the same heuristic: when `output_format` is `None` or
`"auto"`, text responses that start with `{` and end with `}` are tentatively
parsed as JSON. If parsing succeeds, the part is promoted from `TextContent` to
`JsonContent`. When `output_format == "json"`, parsing is always attempted and
a failure falls back to `TextContent` with a warning.

## Tool call flow

The full tool call lifecycle across the message model:

```
1. LLMTask sends ChatCompletionRequest with tools={...}
2. Provider returns ChatCompletionResponse with ToolCallContent parts
3. Agent extracts each ToolCallContent, creates a ToolCallTask
4. ToolCallTask:
   a. Emits ToolCallContent with require_approval=True (if HITL enabled)
   b. HITL controller approves/rejects
   c. Invokes the tool, produces a ToolCallResultContent
   d. Appends both ToolCallContent + ToolCallResultContent to message history
5. LLMTask re-sends with updated history (provider maps them back to wire format)
6. Repeat until no more tool calls or MAX_TOOL_CALLS reached
```
