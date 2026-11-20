# Workers — Internals

A worker runs one agent unattended: it answers the agent's
[mail](ibc.md#agent-mail) until it is stopped. This page covers the serve
loop, the heartbeat, tool approval and the `ask` helper. For usage, see the
[user guide](../user-guide/workers.md) and the
[CLI reference](../cli-reference/worker.md).

Source: `src/geenii/worker.py`, CLI in `src/geenii/cli/worker_cli.py`
(`geenii worker`).

## The serve loop

`serve(spec, model=None, *, poll_seconds=2.0, once=False, approval_policy="none") -> int`
runs in the foreground of the calling thread:

1. Builds the approval controller from `approval_policy` (see
   [Tool approval](#tool-approval)), opens the agent's `Mailbox`, and installs
   SIGTERM and SIGINT handlers that set a stop flag. Signal handlers can only
   be installed from the main thread, so `serve` must run there.
2. Starts the [heartbeat](#heartbeat), then runs `recover()` once, including
   messages held under its own instance id (they can only come from an earlier
   process with the same id), see [Delivery](#delivery).
3. Loop until the stop flag is set:
   - every `HEARTBEAT_SECONDS`, `recover()` again;
   - `mailbox.claim_next(owner=instance)`, which moves the message to
     `processing/<instance>/`; with no message, exit if `once`, else sleep
     `poll_seconds` and try again.
   - `handle(spec, message, model, approver)`: a new agent from
     `init_agent(spec, model=model, memory=ShortTermChatMemory(), hitl=approver)`,
     so no state carries over between messages, and
     `agent.process(prompt)` with the prompt
     `Message from agent '<from>' (subject: <subject>):\n\n<body>`. If the
     message has [attachments](ibc.md#attachments), the prompt ends with
     `Attached files (in the shared file store; use file_read_text or
     file_download with the id):` and one `- name (id, size)` line per file.
     To open them, the agent's spec must list those tools and `--approve`
     must allow them.
     An exception becomes the answer `Error while handling your message: <e>`.
   - `reply(spec, message, answer)`, see [Replies](#replies), then
     `mailbox.ack()`, which moves the message to `read/`. If the reply raises,
     the error is logged as `message.reply_failed` and `mailbox.fail()` moves
     the message to `failed/`; the loop goes on. If that move fails, it is
     logged as `message.finish_failed` and the message stays in `processing/`
     until the instance is gone.
4. On exit (also on an exception): restores the previous signal handlers,
   stops the heartbeat and removes its file.

A signal sets the flag only; the current message is finished before the loop
ends.

The instance id is `<hostname>-<pid>` (`instance_id()`).

### Log events

`log(event, **fields)` prints one JSON object per line to stdout, with `ts`
and `event`:

| Event | Fields |
|---|---|
| `worker.start` | `agent`, `instance`, `model` (`default` if not given), `approval` (the effective policy) |
| `message.start` | `agent`, `instance`, `id`, `sender`, `subject` |
| `message.reply_failed` | `agent`, `instance`, `id`, `error` |
| `message.finish_failed` | `agent`, `instance`, `id`, `error` |
| `message.recovered` | `agent`, `instance`, `id`, `owner` (the dead instance), `answered`, `notified` (the sender was told) |
| `message.done` | `agent`, `instance`, `id`, `ok` (false if the agent raised), `seconds`, `replied` |
| `worker.stop` | `agent`, `instance`, `handled` |

## The answer

`final_answer(messages)` picks the reply text from the messages the agent
yielded, newest first:

- an assistant `ModelMessage` with a `JsonContent` part → the first JSON part,
  pretty-printed;
- an assistant `ModelMessage` with text → its `TextContent` parts joined;
- a `SystemMessage` with `level == "error"` and text → `Error: <text>`. It only
  counts if no answer comes after it, since then the run failed;
- info and warning `SystemMessage`s are skipped, so a status note never
  replaces the answer;
- nothing found → `(no answer)`.

Assistant messages without text or JSON (tool calls, approval requests) are
skipped.

## Replies

`reply(spec, message, answer) -> bool` mails the answer to the sender and
returns `True`, or returns `False` without sending when the message must not
be answered:

- it is a reply itself (`reply_to` is set), so two workers can't answer each
  other's answers forever;
- it is from the worker's own agent;
- the sender is not in `known_agents()` (registry agents plus `human`).

Before sending, an empty answer becomes `(no answer)` (`Mailbox.send` rejects
an empty body), an answer over `MAX_TEXT` is cut and ends with
`... [truncated]`, and the subject `Re: <subject>` is cut to `MAX_SUBJECT`.
The reply's `reply_to` is the message id.

## Tool approval

Every tool call of an agent goes through its HITL controller (see
[agents](agents.md#human-in-the-loop-hitl)). `serve` passes a
`PolicyHumanInTheLoopController` (`geenii/hitl.py`), built with
`PolicyHumanInTheLoopController.from_policy(policy)`:

| Policy | `allowed` | Approves |
|---|---|---|
| `none`, empty or `None` | `set()` | nothing |
| `all` | `None` | every tool call |
| `a,b` | `{"a", "b"}` | calls of the listed tools only |

`describe()` returns the effective policy (`none`, `all` or the sorted list),
which `worker.start` logs. A denied call reaches the model as a tool result
with an error, and the agent continues without it.

The CLI reads the policy from `--approve`, else `GEENII_APPROVE`, else `none`.

## Heartbeat

`Heartbeat(agent, instance, interval=HEARTBEAT_SECONDS)` keeps a status file
at `$GEENII_HOME/workers/<agent>/<instance>.json`:

```json
{"agent": "research", "instance": "myhost-4242", "pid": 4242,
 "started": "2026-11-20T09:00:00+00:00", "handled": 3, "status": "busy",
 "message_id": "3f2a9c1b7d4e", "busy_since": "2026-11-20T09:30:12+00:00",
 "last_seen": "2026-11-20T09:31:27+00:00"}
```

- `start()` writes the file and starts a daemon thread that rewrites it every
  `interval` seconds (`HEARTBEAT_SECONDS = 15`), so a worker that spends
  minutes on one message still shows as alive. A failed write is ignored; the
  next one tries again.
- `beat(**changes)` updates the state and `last_seen` and writes the file
  atomically (temp file + `os.replace`). A lock serialises the thread and the
  main loop.
- The loop sets `status` to `idle` before each inbox check, to `busy` (with
  `message_id` and `busy_since`) while handling a message, and increments
  `handled` after it. The initial status is `starting`.
- `remove()` stops the thread, waits for it, then deletes the file.

`list_workers(stale_seconds=STALE_SECONDS)` reads all status files, adds
`seconds_since_seen` and `alive` (`seconds_since_seen <= stale_seconds`;
`STALE_SECONDS = 60`, four missed beats) and skips files it can't parse. A
killed worker leaves its file behind, shown as not alive; delete it by hand.
Times are stored to the second.

## `ask`

`ask(agent, text, *, sender="human", subject=None, timeout=300, poll_seconds=1.0) -> dict | None`
sends `text` (subject: the first line, up to 80 characters) and polls the
sender's unread mail for a message whose `reply_to` is the sent id. It reads
that reply (marking it read) and returns it, or returns `None` after
`timeout`. Other unread mail is left alone. It needs a running worker for
`agent`; the sent message stays in the agent's inbox after a timeout.

## Delivery

Each message is handled **at most once**, and a message is never lost
silently: it ends in `read/` (answered) or `failed/` (not answered), and the
sender learns about a failure.

While a worker works on a message, the message is leased to it in
`inbox/<agent>/processing/<instance>/` (see [IBC](ibc.md#leases)).
`recover(spec, instance, include_self=False)` takes over the messages of dead
instances. `instance_alive(agent, instance)` decides; an instance is dead if:

- its heartbeat file is missing or unreadable (a worker removes it only on
  exit, when it holds no message),
- its `last_seen` is older than `STALE_SECONDS`, or
- it ran on this host (`<host>-<pid>` with this hostname) and its pid no
  longer exists. A crash on the same machine is found at the next recovery,
  without waiting for the heartbeat to go stale.

For each message of a dead instance:

- if the sender's inbox already holds a reply to it (`find_reply()`; the
  worker died after replying but before `ack()`), it moves to `read/`;
- otherwise it moves to `failed/` and the sender gets a reply saying the
  message could not be answered and will not be retried, if the
  [reply rules](#replies) allow one. This also ends a waiting `ask()`.

Messages are never put back into the inbox. A message that crashes the
process can't take down the next worker, and nothing is answered twice. To
try a failed message again, send it again.

Recovery runs only in workers of the same agent. A message held by a dead
worker stays in `processing/` until a worker of that agent runs again.

## Programmatic use

```python
from geenii.g import get_agent_registry
from geenii.worker import serve

spec = get_agent_registry().get_config("research")
serve(spec, approval_policy="mcp__paper_search__search_arxiv", once=True)
```

Call `serve` from the main thread. To test the loop without a model, replace
`geenii.worker.handle` with a function that returns a string.
