# Usage Tracking

Geenii records token usage for **chat and text completions** in an
append-only JSONL log. There is no database, no cost calculation, no limit or
quota, and no HTTP endpoint. The only reader is the agents' `/usage` command.

This page describes the current implementation, including its gaps.

## Overview

```
provider.generate_chat_completion()      build response.usage (a Usage object, or None)
provider.generate_completion()
        │
geenii.ai.generate_chat_completion()     the only two places usage is recorded
geenii.ai.generate_completion()
        ├─ _ai_log("completion.request" / "completion.response" / "completion.error")
        │                                                          → logs/ai-YYYY-MM-DD.log  (chat only, plus errors)
        └─ _ai_usage_log(provider, model, context_id, usage,       → logs/ai-usage-YYYY-MM.log
                         source=…, task=…, error=…)
        │
/usage agent command                      scans ai-usage-*.log for the conversation's context id
```

## 1. Providers report usage

Each provider sets `usage` on its `CompletionResponse`
(`geenii/datamodels.py`; `ChatCompletionResponse` inherits it) to a `Usage`
object, or leaves it `None` if it has no usage to report.

### The `Usage` model

`Usage` is **normalised**: every provider maps its own counts to one
convention, so values from different providers can be summed:

- `input_tokens` counts **all** input tokens the model processed, cached or
  not.
- `cache_read_input_tokens` and `cache_creation_input_tokens` are the
  **parts** of `input_tokens` read from or written to the prompt cache.
  `None` means the provider does not report them.
- `total_tokens` is input + output, so it includes cached input.
- `uncached_input_tokens` (a property, not stored) is input minus both cache
  parts.

| Field | Type | Set by |
|---|---|---|
| `input_tokens`, `output_tokens` | `int`, default `0` | all providers |
| `total_tokens` | `int`; **input + output** if not given | all; openai passes its own total |
| `cache_read_input_tokens` | `int \| None`, part of `input_tokens` | anthropic, openai |
| `cache_creation_input_tokens` | `int \| None`, part of `input_tokens` | anthropic |
| `load_duration`, `input_duration`, `output_duration`, `total_duration` | `int \| None`, milliseconds | ollama |

Fields a provider does not report stay `None`. Unknown keys are ignored when
parsing (`extra="ignore"`), so old log lines and newer keys both load. To add
a provider-specific metric, add an optional field here rather than putting a
loose key in a dict.

| Provider | Fields set | Chat | Text | Notes |
|---|---|---|---|---|
| `anthropic` | tokens, cache tokens | yes | — | Anthropic reports the uncached input as `input_tokens` and cache writes and reads separately; `_usage_from_result` sums them into `input_tokens`. Text completions are not implemented, so they always fail (and are logged as failed) |
| `openai` | tokens, cache reads | yes | yes | Responses API `usage` (`_usage_from_result`); `None` if the result has none. OpenAI's `input_tokens` already includes cached input; `input_tokens_details.cached_tokens` becomes `cache_read_input_tokens`. OpenAI does not report cache writes |
| `ollama` | tokens (`prompt_eval_count`, `eval_count`), durations | yes | yes | `_usage_from_result`, shared by chat and text. Missing or `null` counts (e.g. a cached prompt) count as 0 |
| `fake` | `input_tokens=10`, `output_tokens=20` (total 30) | yes | yes | Fixed values, for tests |
| `geenii` | — | — | — | Both raise `NotImplementedError` |

In API responses (`/ai/completion`, `/ai/chat/completion`) `usage` is the
full object, with unset fields as `null`.

The providers also log the token count of chat completions at `INFO` level
("Tokens used in this chat completion: …").

## 2. Writing the logs

Two functions in `geenii/ai.py` record usage. Both take keyword-only, optional
`source` and `task` arguments, which are used only for the usage log; callers
pass them explicitly (see [section 3](#3-what-gets-recorded)).

**`generate_chat_completion(request, tool_registry, *, source, task)`:**

1. Sets a `context_id` on the request if it has none (`uuid4`). This happens
   before anything can fail, so failed calls are attributed too. It also
   copies the id to the response.
2. Appends the full request and response to `ai-YYYY-MM-DD.log` (`_ai_log`).
   The response includes `usage` and the raw `model_result`.
3. Appends one usage line to `ai-usage-YYYY-MM.log` (`_ai_usage_log`).
4. On any exception (an invalid model id, an unknown provider, a provider
   error), it writes a `completion.error` entry and a usage line with
   `usage: {}` and an `error` (`_log_failed_call`), then **re-raises** the
   original exception.

**`generate_completion(model, prompt, stream, *, source, task, **kwargs)`:**
the same, except:

- There is no context id, so the usage line has `context_id: null`, and
  `/usage` never counts text completions.
- Successful requests and responses are not written to the daily log (only
  errors are).
- On failure it **returns** a `CompletionErrorResponse`, as before, instead of
  raising.

**Logging never breaks a call.** `_ai_log` and `_ai_usage_log` catch every
exception while writing and print it instead. A full disk or a read-only
cache dir therefore neither turns a successful completion into an error nor
replaces the original error of a failed one.

Both files are in `$GEENII_CACHE_DIR/logs/` (default `~/.geenii/.cache/logs/`).

### Usage log format

One JSON object per line, one file per month. The file is named after the
**UTC** month of the line's timestamp, so a line is always in its month's file:

```json
{"timestamp": "2026-10-14T00:22:45.119314+00:00", "provider": "anthropic", "context_id": "d9942e200d5442d1897f398bcf680c8c",
 "model": "claude-opus-4-6", "source": "agent:default", "task": "llm",
 "usage": {"input_tokens": 6136, "output_tokens": 672, "total_tokens": 6808,
           "cache_creation_input_tokens": 1416, "cache_read_input_tokens": 4332},
 "usage_version": 2, "error": null}
```

A text completion:

```json
{"timestamp": "2026-10-14T01:23:09.986384+00:00", "provider": "ollama", "context_id": null,
 "model": "llama3.2:3b", "source": "api", "task": "completion",
 "usage": {"input_tokens": 31, "output_tokens": 3, "total_tokens": 34, "load_duration": 1547,
           "input_duration": 43, "output_duration": 13, "total_duration": 1605},
 "usage_version": 2, "error": null}
```

A failed call:

```json
{"timestamp": "2026-10-14T01:10:02.512211+00:00", "provider": "ollama", "context_id": "d9942e200d5442d1897f398bcf680c8c",
 "model": "qwen3:8b", "source": "agent:default", "task": "llm", "usage": {},
 "usage_version": 2, "error": "ConnectionError: Failed to connect to Ollama…"}
```

| Field | Meaning |
|---|---|
| `timestamp` | UTC, ISO 8601 with offset (`…+00:00`); `datetime.fromisoformat()` returns an aware datetime |
| `provider`, `model` | From the `provider:model` id; `model` is without the provider prefix. If the id is invalid, `provider` is `null` and `model` is the id as given |
| `context_id` | The request's context id (see below); `null` for text completions |
| `source` | Who made the call: `agent:<name>`, `api`, `cli` or `bot:<class>`; `null` if the caller passed none |
| `task` | What the call was for (see the table below); `null` if the caller passed none |
| `usage` | `Usage.model_dump(exclude_none=True)`: only the fields the provider set, so the keys still differ per provider. `{}` if there was no usage or the call failed. Read it back with `Usage.from_log_entry(line)` (not `model_validate`), which converts older versions |
| `usage_version` | The convention of `usage` (`USAGE_VERSION` in `datamodels.py`, currently `2`); missing means version 1, see below |
| `error` | `null` on success. For a failed call: `"<ExceptionType>: <message>"` on one line, at most 500 characters (`_error_text`) |

**Usage versions.** Version 2 (all current lines) follows the normalised
convention above. In version 1 lines (no `usage_version`), Anthropic's
`input_tokens` and `total_tokens` leave out the cache reads and writes.
`Usage.from_log_entry` adds them back for `provider == "anthropic"`. Version
1 lines of other providers already match version 2. If you change what a
`Usage` field means, bump `USAGE_VERSION` and convert the older lines in
`from_log_entry`.

Lines written before `source`, `task` and `error` were added do not have these keys.
Readers should treat a missing key like `null`. Those older lines also have
**local** timestamps without an offset, and their files are named after the
local month. A reader that compares times should treat a timestamp without an
offset as local time (`datetime.fromisoformat(ts).astimezone()`).

Lines are written with a plain `open(…, "a")` (`utils/json_util.append_jsonl`)
without a lock. Each line is a single small write, so concurrent writers
(several chat turns, server and CLI) do not interleave in practice. Readers
should still skip lines that are not valid JSON.

## 3. What gets recorded

| Caller | Recorded | `context_id` | `source` | `task` |
|---|---|---|---|---|
| `LLMTask`: agent turns, including each follow-up call after tool results | yes | the agent's `context_id` | `agent:<name>` | `llm` |
| `FindBestSkillTask`: skill selection, only with 2 or more skills and no trigger match | yes | the agent's `context_id` | `agent:<name>` | `skill_select` |
| `FindBestAgentTask` (`RoutingAgent`) | yes | the agent's `context_id` | `agent:<name>` | `agent_select` |
| `ToolFilterTask` (currently unused) | yes | the agent's `context_id` | `agent:<name>` | `tool_filter` |
| `MemoryCompactionTask` (`/compact` summary) | yes | the context being compacted, i.e. the id *before* the rotation to `-<n>` | `agent:<name>` | `compact` |
| `POST /api/v1/ai/chat/completion` | yes | the request's `context_id`, or a new hex id | `api` | `chat_completion` |
| `POST /api/v1/ai/completion` (text) | yes | `null` | `api` | `completion` |
| `geenii ai chat` (`cli/ai_cli.py`) | yes | random | `cli` | `chat` |
| `geenii ai completion` (text) | yes | `null` | `cli` | `completion` |
| `example_bots.py` bots | yes | random | `bot:<class>` | `chat` |
| Image, speech, transcription | **no** | — | — | — |
| Failed calls of any caller above | yes, with `error` and `usage: {}` | as for that caller | as for that caller | as for that caller |

`agent:<name>` comes from `_usage_source()` in `agent/tasks.py`.
`tests/geenii/test_task_context_id.py` checks the `context_id`, `source` and
`task` of every agent task. A new caller of `generate_chat_completion` or
`generate_completion` should pass both `source` and `task`.

Agent context ids: `BaseAgent` defaults to `uuid7().hex`. `/chats` sessions
use the session id. `/compact` moves the agent to `<context_id>-<n>`
(`MemoryCompactionTask._next_generation`), so one conversation can span
several ids.

## 4. Reading usage: `/usage`

The agent command `/usage` (`report_usage` in
`geenii/agent/info_commands.py`, see [agents.md](agents.md#info-commands)):

1. Strips any `-<n>` compaction suffixes from the agent's `context_id` to get
   the root id.
2. Scans **all** `ai-usage-*.log` files line by line. A cheap substring check
   comes before the JSON parse.
3. Keeps entries whose `context_id` matches `^<root>(-\d+)*$`.
4. Parses each line with `Usage.from_log_entry`, which converts version 1
   Anthropic lines. A malformed one counts as a call without tokens. Groups
   by `provider:model`, and
   separately by `task`, and sums the calls and every `*tokens` field. Lines
   without a `task` count as `untagged`.
5. Shows a table of calls, input, output and total tokens per model. If more
   than one task occurs, it adds a **By purpose** table (for example `llm`
   vs. `skill_select`). If the prompt cache was used, a line gives the share
   of input read from it and the tokens written to it, e.g. "8,496 of
   18,249 input tokens (46%) were read from the prompt cache; 4,248 were
   written to it."
   Failed calls count as calls with 0 tokens, and a line says how many
   failed.

The reply is not stored in the agent's memory.

Every model call an agent task makes passes the agent's `context_id`, so
`/usage` includes skill and agent selection and `/compact` summaries.

Limitations:

- A handoff (`@agent`) runs another agent with its own context id, and its
  usage is not counted here.
- A conversation id that itself ends in `-<digits>` is treated as a
  compaction successor of its prefix.
- Cost grows with the total log size, because every month is scanned on each
  call.

## 5. Usage on messages

`ModelMessage.usage` holds the usage of the model call that produced the
message. The rule is the same as in [messages.md](messages.md#modelmessage-geeniidatamodelspy):
only the first message of each response carries it. It is stored in the
conversation memory and streamed to `/chats` clients (`usage` on the
`message` of a `message` event; typed as `Usage` in
`geenii-ui/src/components/xchat/chat.types.ts`).

This is a second, per-conversation copy of the numbers. The usage log stays
the source for totals across conversations, and for calls that create no
message, such as skill and agent selection, tool filtering and text
completions. Summing a conversation's message usage therefore gives only the
calls that produced messages, which is less than `/usage`. Messages stored
before this field existed have `usage: null`.

## 6. Usage on the agent

`BaseAgent.usage` and `BaseAgent.model_calls` count every successful model
call the agent instance makes. All agent tasks go through `_complete()` in
`agent/tasks.py`, which calls `record_usage()`. A handoff adds the
sub-agent's totals, so unlike `/usage` these counters include handoffs.
They live in memory only, starting at 0 when the agent is created, and `/self`
shows them. See [agents.md](agents.md#usage).

| Where | Scope | Persisted | Includes |
|---|---|---|---|
| Usage log (`/usage`) | all calls, any conversation | yes | everything except handoffs (other context id) |
| `ModelMessage.usage` | one model call | with the conversation | only calls that produced a message |
| `Agent.usage` | one agent instance | no | all of the agent's calls, plus handoffs |

## Not implemented

- **Costs:** there is no price table, and tokens are never turned into money.
- **Aggregation:** the log has the data to split usage per agent (`source`),
  purpose (`task`), model and day, but nothing reads it across
  conversations, and there is no API or UI. The web UI shows no usage; the
  `usage` fields in `geenii-ui/src/api/openai.types.ts` are unused type
  declarations.
- **Retention:** the log files are never rotated or pruned.
- **Limits:** no budgets, quotas or rate limits.
- **Streaming:** the providers do not stream, so usage is only known when the
  call finishes.
- **Media:** image, speech and transcription calls are not logged.

## Improvement ideas

1. If usage is ever shown in the UI, add an aggregation endpoint
   (`GET /api/v1/ai/usage?source=agent:<name>&from=…&group_by=task`) instead of
   reading the logs in several places. It should read lines with
   `Usage.from_log_entry`.
2. A handoff could tag the sub-agent's calls with the parent's conversation,
   so that `/usage` can include them.
