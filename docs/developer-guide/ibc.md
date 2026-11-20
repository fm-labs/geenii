# Inter-Bot Communication (IBC)

`geenii.ibc` lets agents, workers and the human user exchange information
through three file-based channels:

- **Agent mail** — one inbox per agent; direct messages with replies and
  file attachments.
- **Blackboard** — one shared, append-only list of notes under topics.
- **File store** — shared, immutable files referenced by id; each agent's
  *filebox* lists the files it uploaded or received.

All are plain files in `GEENII_HOME`, so they need no daemon or server, work
across processes (and across machines that share the folder), and survive
restarts. [Workers](workers.md) use agent mail to serve agents unattended; the
[`geenii worker`](../cli-reference/worker.md) CLI gives the human access.

Source: `src/geenii/ibc/comms.py` (mail, blackboard) and
`src/geenii/ibc/files.py` (file store).

## Storage

`config.geenii_home()` returns the base folder: `GEENII_HOME` if set, else
`~/.geenii`. It is created on first use.

```
$GEENII_HOME/
├── blackboard.jsonl               # the blackboard, one JSON entry per line
├── files/                         # the file store, see below
│   └── f_<32 hex>/
│       ├── data
│       └── meta.json
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
| `MAX_TEXT` | 20,000 | Message body, blackboard text, `file_read_text` output |
| `MAX_ATTACHMENTS` | 20 | Attachments per message |
| `FILE_ID_RE` | `^f_[0-9a-f]{32}$` | File ids |
| `MAX_FILE_SIZE` | 25 MB | One stored file |
| `MAX_NAME` | 200 | Stored file name (longer names are shortened, keeping the extension) |
| `MAX_NOTE` | 1,000 | A stored file's note |
| `HUMAN` | `"human"` | The user's name as sender, receiver and author |

`check_agent_name()` raises `ValueError` for any other name. Subjects, topics,
bodies and texts are stripped and must not be empty. Every validation error is
a `ValueError`; the CLI shows it as `Error: …`.

Message and blackboard ids are the first 12 hex characters of a UUID4; file
ids are `f_` plus a whole UUID4 in hex, so they can't be guessed.

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
  "reply_to": null,
  "attachments": [
    {"id": "f_6c1d…", "name": "papers.csv", "size": 2048, "mime": "text/csv"}
  ]
}
```

`reply_to` is the id of the message this one answers, or `null`.
`attachments` is only present when files are attached.

### `Mailbox(agent)`

| Method | Does |
|---|---|
| `Mailbox.send(sender, to, subject, body, reply_to=None, attachments=None)` | Static. Validates, writes the message to `.<name>.tmp` in the receiver's inbox, then renames it into place (`os.replace`), so readers never see a half-written file. `attachments` are file ids (see [Attachments](#attachments)). Returns the message |
| `list(include_read=False, preview_chars=0)` | Headers (`id`, `ts`, `from`, `subject`, `reply_to`, `read`, `failed`, `attachments` (a count)) of unread messages, oldest first, optionally with read ones and a body preview. Unreadable files are skipped |
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

### Attachments

`Mailbox.send(..., attachments=[file_id, …])` attaches files of the
[file store](#file-store). After the message itself has passed validation,
it:

1. drops duplicate ids and rejects more than `MAX_ATTACHMENTS`;
2. looks up every id first, so an unknown id fails the whole send and nothing
   is shared;
3. adds the receiver to each file's `shared_with`, so the files show in its
   filebox;
4. stores `{id, name, size, mime}` per file in the message.

The files themselves are not copied into the inbox.

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
agent, which always acts as itself (`COMMS_TOOL_NAMES`):

| Tool | Does |
|---|---|
| `blackboard_post(topic, text)` | Post an entry as the agent |
| `blackboard_read(topic="", limit=20)` | Latest entries; with none, also the list of topics |
| `send_mail(to, subject, body, reply_to="", attachments=[])` | Send mail, optionally with file ids attached; rejects unknown receivers and mail to itself |
| `check_inbox()` | All unread messages in full; they are marked read |
| `read_mail(message_id)` | One message again, read or not |
| `list_agents()` | The other agents and `human`, with descriptions |

`init_agent()` registers the ones an agent spec lists in `tools`, bound to
that agent (`_register_ibc_tools()` in `geenii/g.py`); the same goes for the
[file tools](#file-tools-for-agents). An agent whose name isn't a valid
`AGENT_NAME_RE` name gets none of them, with a warning in the log.

```markdown
---
name: research
tools: [send_mail, check_inbox, file_upload, file_download, file_read_text]
---
```

## File store

Agents share files through one store of immutable files, each referenced by
an id. A file is never changed after upload: a new version is a new upload
with a new id, so an id in a message always means the same content and
readers need no locks.

### Layout

```
$GEENII_HOME/files/
├── f_3f9c0d…e1/
│   ├── data            # the file's bytes
│   ├── meta.json       # see below
│   └── .lock           # held while meta.json is updated (sharing)
├── .tmp-f_…/           # an upload in progress (ignored)
└── .trash-f_…-<rand>/  # a delete in progress (ignored)
```

```json
{
  "id": "f_3f9c0d…e1",
  "name": "papers.csv",
  "size": 2048,
  "sha256": "…",
  "mime": "text/csv",
  "owner": "research",
  "created_at": "2026-11-20T09:40:00+00:00",
  "shared_with": ["writer"],
  "note": "RAG evaluation papers"
}
```

An upload streams into `.tmp-<id>/`, counting the size and hashing on the
way, writes `meta.json`, then renames the folder into place. A file over
`MAX_FILE_SIZE` stops the copy and the temp folder is removed. A delete
renames the folder to `.trash-…` first, then removes it. Readers therefore see
a whole file or none.

### The filebox

An agent's filebox is a view, not a folder: the files whose `owner` is the
agent plus the ones whose `shared_with` lists it. Attaching a file to mail is
what shares it; `FileStore.share()` and `geenii worker files put --share` do
it directly.

### Access

The id is the key: anyone who knows an id can read the file, and only the
owner (or the human through the CLI, as admin) can delete it. `shared_with`
only drives the filebox; it isn't an access check. That is deliberate: all
agents run as the same OS user, so an agent with `bash` could read
`$GEENII_HOME/files` anyway. File ids are random 128-bit values, so they
can't be guessed.

### `FileStore(root=None)`

| Method | Does |
|---|---|
| `put(owner, src, name=None, note="")` | Copies the file `src` into the store under `name` (default: its own). Returns the metadata |
| `put_bytes(owner, data, name, note="")`, `put_text(owner, name, text, note="")` | The same from memory (text as UTF-8) |
| `info(file_id)` | The metadata. `ValueError` for an invalid, unknown or damaged id |
| `exists(file_id)` | `True` if the file is there; `False` also for invalid ids |
| `data_path(file_id)`, `read_bytes(file_id)` | The `data` file's path, or its bytes |
| `read_text(file_id, limit=MAX_TEXT)` | `(text, truncated)`. Decodes UTF-8; `ValueError` for binary files |
| `copy_to(file_id, dest, overwrite=False)` | Copies the file to `dest`, a file path or a folder (then under the file's name). `ValueError` if the target exists and `overwrite` is false |
| `list(agent=None)` | Metadata of all files, newest first, or only `agent`'s filebox. Damaged files are skipped |
| `share(file_id, agents)` | Adds agents to `shared_with` (never the owner, never twice), under the `.lock` file lock |
| `delete(file_id, by=None)` | Deletes the file. `by`, if given, must be the owner; `None` deletes as admin |
| `gc(older_than, keep=None)` | Deletes files older than `older_than` (a `timedelta`), except `keep` and files attached to mail that is unread or claimed by a worker (`attached_to_pending_mail()`). Also removes temp and trash folders that old. Returns the deleted ids |

`clean_name()` keeps only the last path segment of a name and drops control
characters, so a name like `../../etc/passwd` is stored as `passwd`. The
MIME type is guessed from the name.

### File tools for agents

`files_tools(agent_name)` returns six tools bound to one agent
(`FILE_TOOL_NAMES`). Uploads are owned by that agent. Paths are relative to
the agent's working folder (`ctx.cwd`) and must pass the same check as the
`read` and `write` tools (`is_file_in_allowed_dirs()`: the agent's working
folder, `GEENII_WORKING_DIR` or the user settings' `allowed_dirs`; symlinks
are resolved first).

| Tool | Does |
|---|---|
| `file_upload(path, note="")` | Uploads a file from the working folder; returns `{id, name, size, mime, owner, created_at, note}` |
| `file_download(file_id, path="", overwrite=false)` | Copies a stored file into the working folder, by default under its own name; refuses to overwrite unless `overwrite` |
| `file_list()` | The agent's filebox; each entry has `shared: true` if another agent owns it |
| `file_info(file_id)` | Metadata including `sha256` and `shared_with`, without the content |
| `file_save_text(name, text, note="")` | Stores text as a new file, for agents without file system tools |
| `file_read_text(file_id)` | Up to `MAX_TEXT` characters of a text file, with a `truncated` note if there is more |

Errors (unknown id, path not allowed, binary file, …) come back as tool
errors (`is_error`), not exceptions. `init_agent()` registers the ones a
spec lists in `tools`, as for the [mail tools](#tools-for-agents).

## Formatting helpers

`format_inbox(headers)` and `format_blackboard(entries)` render headers and
entries as plain text for the CLI (`No unread mail.`, `The blackboard is
empty.` when empty); `format_inbox` adds `[n files]` for messages with
attachments. In `files.py`, `format_attachments(attachments)` renders one
`- name (id, size)` line per file, and `format_size()` a byte count.

## Known limitations

- **No retry:** a message whose worker crashes ends in `failed/` and is not
  handled again; see [workers](workers.md#delivery).
- **No automatic cleanup:** `read/` and `failed/` folders and the blackboard
  grow forever. Stored files are only removed by `geenii worker files gc` or
  `rm`.
- **No deduplication or quotas:** uploading the same content twice stores it
  twice, and only the per-file size is limited.
- **No access control:** any process that can write `GEENII_HOME` can send
  mail as any name, post as any author, or read any stored file. The sender
  name is not authenticated (see [Access](#access)).
- **Polling only:** there is no notification; readers check the folder.
