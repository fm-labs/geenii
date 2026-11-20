# geenii worker

Run unattended agent instances (workers), and take part in agent mail and the
shared blackboard as the human user.

## Synopsis

```
geenii worker <command> [OPTIONS]
```

Agent mail, the blackboard and the worker status files live in `GEENII_HOME`
(default `~/.geenii`), see [Configuration](../user-guide/configuration.md).
Every command works without the [daemon](daemon.md). For background and
examples, see the [workers user guide](../user-guide/workers.md).

To list agents use [`geenii agents list`](agents.md); to chat with one use
[`geenii agent`](agent.md).

## Commands

### serve

```
geenii worker serve <AGENT> [--model M] [--approve POLICY] [--poll S] [--once]
```

Run a worker for `AGENT` in the foreground. It takes the messages in the
agent's inbox one at a time, answers each with a fresh agent instance, and
mails the answer back to the sender. Several workers of the same agent can
share one inbox; each message is handled by one of them.

The worker prints one JSON log line per event to stdout (`worker.start`,
`message.start`, `message.done`, `message.reply_failed`, `worker.stop`). Stop
it with Ctrl-C or SIGTERM: the message it is working on is finished first.

| Option | Short | Description |
|---|---|---|
| `--model` | `-m` | Model id, e.g. `ollama:qwen3:8b` (default: the agent's model) |
| `--approve` | | Which tool calls to allow: `none` (default), `all`, or a comma-separated list of tool names (env: `GEENII_APPROVE`) |
| `--poll` | | Seconds between inbox checks (default 2) |
| `--once` | | Stop when the inbox is empty |

Nobody is there to approve tool calls, so the policy decides. With the
default `none`, the agent can't call any tool.

A message is answered at most once. If a worker dies while working on a
message, the next worker of the same agent moves it to `failed/` and tells the
sender; it is not retried. A message whose reply can't be sent also ends in
`failed/`.

Exits with code 1 for an unknown agent.

### ask

```
geenii worker ask <AGENT> <TEXT ...> [--from NAME] [--timeout S]
```

Mail `TEXT` to `AGENT` and wait for the reply of a running worker, then print
the reply's body. The subject is the first line of the text (up to 80
characters). The reply is marked read in your inbox.

| Option | Description |
|---|---|
| `--from` | Sender name (default `human`); the reply goes to this inbox |
| `--timeout` | Seconds to wait for the reply (default 300) |

Exits with code 1 if no reply arrives in time. The message stays in the
agent's inbox, so a worker started later still answers it; the reply then
shows up in `geenii worker inbox`.

### list

```
geenii worker list
```

Show the workers as a table: agent, instance (`<host>-<pid>`), status, number
of messages handled and start time. The status is `starting`, `idle`,
`busy <time>` (how long it has been working on the current message), or
`gone?` when the worker hasn't updated its status file for 60 seconds, which
usually means it was killed.

### inbox

```
geenii worker inbox [AGENT] [--read ID] [--all]
```

List the unread mail of `AGENT`, oldest first (default: your own inbox,
`human`). With `--read`, show one message in full and mark it read.

| Option | Description |
|---|---|
| `--read ID` | Show the message with this id (12 hex characters) and mark it read |
| `--all` | Also list read and failed messages (marked `(read)` and `(failed)`) |

### send

```
geenii worker send <TO> <SUBJECT> <BODY> [--from NAME]
```

Put a message into the inbox of `TO`, an agent name or `human`. It is
answered once a worker for that agent runs.

| Option | Description |
|---|---|
| `--from` | Sender name (default `human`) |

Exits with code 1 for an unknown receiver or an empty or too long subject
(max 200 characters) or body (max 20,000).

### blackboard

```
geenii worker blackboard [--topic T] [--limit N]
```

Show the latest blackboard entries, oldest first. Without `--topic`, also
list all topics with their number of entries.

| Option | Short | Description |
|---|---|---|
| `--topic` | `-t` | Only entries with this topic (case-insensitive) |
| `--limit` | `-n` | Maximum number of entries (default 20) |

### post

```
geenii worker post <TOPIC> <TEXT> [--as NAME]
```

Add an entry to the blackboard.

| Option | Description |
|---|---|
| `--as` | Author name (default `human`) |

## Examples

```bash
# Start a worker that may only use one tool
geenii worker serve research --approve mcp__paper_search__search_arxiv

# In another terminal: ask it something and wait for the answer
geenii worker ask research "Find recent papers on speculative decoding"

# Or send mail and read the answer later
geenii worker send research "papers" "Find recent papers on speculative decoding"
geenii worker inbox
geenii worker inbox --read 3f2a9c1b7d4e

# See which workers run
geenii worker list

# Answer what is in the inbox, then exit (e.g. from the scheduler)
geenii worker serve research --once

# Share notes on the blackboard
geenii worker post monthly-report "Numbers for October are in."
geenii worker blackboard --topic monthly-report
```

## See Also

- [Workers](../user-guide/workers.md) — how workers and agent mail fit together
- [Inter-bot communication](../developer-guide/ibc.md) — mail and blackboard internals
- [Workers internals](../developer-guide/workers.md)
