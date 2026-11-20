# Inter-Bot Communication (IBC)

`geenii.ibc` lets agents, workers and the human user exchange information
through two file-based channels:

- **Agent mail** — one inbox per agent; direct messages with replies.
- **Blackboard** — one shared, append-only list of notes under topics.

Both are plain files in `GEENII_HOME`, so they need no daemon or server, work
across processes (and across machines that share the folder), and survive
restarts. [Workers](workers.md) use agent mail to serve agents unattended; the
[`geenii worker`](../cli-reference/worker.md) CLI gives the human access.

Source: `src/geenii/ibc/comms.py`.

## Storage

`config.geenii_home()` returns the base folder: `GEENII_HOME` if set, else
`~/.geenii`. It is created on first use.

```
$GEENII_HOME/
├── blackboard.jsonl               # the blackboard, one JSON entry per line
└── inbox/
    └── <agent>/
        ├── 20261120T093012123456Z-3f2a9c1b7d4e.json   # unread message
        ├── .20261120T...-<id>.json.tmp                  # being written (ignored)
        ├── processing/
        │   └── <owner>/                                 # claimed by a worker instance
        │       └── 20261120T091500000000Z-77d0a3e5c912.json
        ├── read/
        │   └── 20261120T080501000000Z-a81c0e2f9b33.json # read or answered
        └── failed/
            └── 20261120T070000000000Z-0b6e2d4f8a10.json # claimed but not answered
```

## Names and limits

| Constant | Value | Applies to |
|---|---|---|
| `AGENT_NAME_RE` | `^[a-z0-9][a-z0-9_-]{0,63}$` | Senders, receivers, blackboard authors (they become folder names) |
| `MAX_SUBJECT` | 200 | Message subject |
| `MAX_TOPIC` | 100 | Blackboard topic |
| `MAX_TEXT` | 20,000 | Message body, blackboard text |
| `HUMAN` | `"human"` | The user's name as sender, receiver and author |

`check_agent_name()` raises `ValueError` for any other name. Subjects, topics,
bodies and texts are stripped and must not be empty. Every validation error is
a `ValueError`; the CLI shows it as `Error: …`.

Ids are the first 12 hex characters of a UUID4.

## Agent mail

### Message format

```json
{
  "id": "3f2a9c1b7d4e",
  "ts": "2026-11-20T09:30:12+00:00",
  "from": "human",
  "to": "research",
  "subject": "rag papers",
  "body": "Summarize the latest papers on RAG evaluation",
  "reply_to": null
}
```

`reply_to` is the id of the message this one answers, or `null`.

### `Mailbox(agent)`

| Method | Does |
|---|---|
| `Mailbox.send(sender, to, subject, body, reply_to=None)` | Static. Validates, writes the message to `.<name>.tmp` in the receiver's inbox, then renames it into place (`os.replace`), so readers never see a half-written file. Returns the message |
| `list(include_read=False, preview_chars=0)` | Headers (`id`, `ts`, `from`, `subject`, `reply_to`, `read`) of unread messages, oldest first, optionally with read ones and a body preview. Unreadable files are skipped |
| `read(message_id)` | The full message, wherever it is; an unread one is moved to `read/` first. Raises `ValueError` for an invalid or unknown id |
| `claim_next(owner=None)` | Takes the oldest unread message and returns it, or `None` if there is none. Without `owner` it moves to `read/` at once; with `owner` to `processing/<owner>/` (a lease, see below) |
| `ack(message_id, owner)` | Moves a message held by `owner` to `read/`; `False` if `owner` doesn't hold it |
| `fail(message_id, owner)` | Moves a message held by `owner` to `failed/`; `False` if `owner` doesn't hold it |
| `owners()` | The owners that hold messages |
| `recover(is_alive, was_answered=None)` | For every owner where `is_alive(owner)` is false, moves its messages to `read/` if `was_answered(message)` is true, else to `failed/`. Returns `(owner, message, answered)` triples |
| `find_reply(message_id)` | A message in this inbox (unread or read) whose `reply_to` is `message_id`, or `None` |

`list(include_read=True)` also returns the messages in `failed/`; headers
have `read` and `failed` flags.

Files are named `<UTC timestamp>-<id>.json`, so sorting by name is sorting by
time. Taking a message is an atomic rename into `read/`: when several
processes read the same inbox, each message goes to exactly one of them; a
loser of the race gets `FileNotFoundError` internally and moves on to the next
file.

`Mailbox.send` doesn't check that the receiver exists; callers do (see
`known_agents()`).

### Leases

A worker claims with its instance id as `owner` (`OWNER_RE`:
`^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$`), so a message it works on sits in
`processing/<owner>/`. When it is done it calls `ack()` (answered, `read/`)
or `fail()` (not answered, `failed/`). If the owner dies in between,
`recover()` takes the message over: messages are never put back in the
inbox, so none is handled twice. Every move is an atomic rename, so workers
recovering at the same time each move a message at most once. See
[workers](workers.md#delivery) for how workers decide that an owner is dead.

### `known_agents()`

Returns `{name: description}` for every agent in the global agent registry
(`g.get_agent_registry()`, see [agents](agents.md#agent-registry)) plus
`human`. The CLI and the `send_mail` tool use it to reject unknown receivers;
[workers](workers.md) only reply to senders in it.

## Blackboard

### Entry format

One JSON object per line in `blackboard.jsonl`:

```json
{"id": "c5bb31850e1b", "ts": "2026-11-20T09:31:00+00:00", "author": "human", "topic": "monthly-report", "text": "Numbers for October are in."}
```

### `Blackboard(path=None)`

| Method | Does |
|---|---|
| `post(author, topic, text)` | Validates and appends one line. Holds an exclusive `flock` while writing, so parallel writers never interleave lines. Returns the entry |
| `read(topic=None, limit=20, author=None)` | The latest `limit` entries, oldest first, optionally only one topic (case-insensitive) or author. Holds a shared lock while reading. Damaged lines are skipped |
| `topics()` | `{topic: number of entries}` |

`path` defaults to `$GEENII_HOME/blackboard.jsonl`. The file is never
compacted; every read parses all of it.

On Windows there is no `fcntl`, so no lock is taken; appending one short line
is still atomic in practice.

## Tools for agents

`comms_tools(agent_name)` returns six `PythonFunctionTool`s bound to one
agent, which always acts as itself:

| Tool | Does |
|---|---|
| `blackboard_post(topic, text)` | Post an entry as the agent |
| `blackboard_read(topic="", limit=20)` | Latest entries; with none, also the list of topics |
| `send_mail(to, subject, body, reply_to="")` | Send mail; rejects unknown receivers and mail to itself |
| `check_inbox()` | All unread messages in full; they are marked read |
| `read_mail(message_id)` | One message again, read or not |
| `list_agents()` | The other agents and `human`, with descriptions |

These tools are **not registered** with any agent yet: neither `init_agent()`
nor a spec's `tools` list adds them. To use them, register them in the agent's
tool registry and list their names in the spec's `tools`.

## Formatting helpers

`format_inbox(headers)` and `format_blackboard(entries)` render headers and
entries as plain text for the CLI (`No unread mail.`, `The blackboard is
empty.` when empty).

## Known limitations

- **No retry:** a message whose worker crashes ends in `failed/` and is not
  handled again; see [workers](workers.md#delivery).
- **No cleanup:** `read/` and `failed/` folders and the blackboard grow
  forever.
- **No access control:** any process that can write `GEENII_HOME` can send
  mail as any name or post as any author. The sender name is not
  authenticated.
- **Polling only:** there is no notification; readers check the folder.
