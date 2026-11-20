# Inter-Bot Communication (IBC)

`geenii.ibc` lets agents, workers and the human user exchange information
through three channels:

- **Agent mail** — one inbox per agent; direct messages with replies and
  file attachments.
- **Channels** — group messages that everyone can read, sent to a recipient
  starting with `@`. The **blackboard** is the channel `@blackboard`: notes
  under topics.
- **File store** — shared, immutable files referenced by id; each agent's
  *filebox* lists the files it uploaded or received.

All live in `GEENII_HOME`: mail and channels in one SQLite database, the file
store as plain files. They need no daemon or server, work across processes on
one machine, and survive restarts. [Workers](workers.md) use agent mail to
serve agents unattended; the
[`geenii worker`](../cli-reference/worker.md) CLI gives the human access.

Source: `src/geenii/ibc/comms.py` (mail, channels, blackboard),
`src/geenii/ibc/mailstore.py` (storage of mail and channels),
`src/geenii/ibc/filestore.py` (file store) and `src/geenii/storage/filestorage.py`
(storage of files).

## Storage

`config.geenii_home()` returns the base folder: `GEENII_HOME` if set, else
`~/.geenii`. It is created on first use.

```
$GEENII_HOME/
├── files/                         # the file store, see below
│   └── f_<32 hex>/
│       ├── data
│       └── meta.json
└── mail.db                        # mail and channel posts of all agents (SQLite, WAL mode)
```

## Names and limits

| Constant | Value | Applies to |
|---|---|---|
| `AGENT_NAME_RE` | `^[a-z0-9][a-z0-9_-]{0,63}$` | Senders, receiving agents, file owners |
| `CHANNEL_RE` | `^@[a-z0-9][a-z0-9_-]{0,63}$` | Channel names, e.g. `@blackboard` (`BLACKBOARD`) |
| `MAX_SUBJECT` | 200 | Message subject |
| `MAX_TOPIC` | 100 | Blackboard topic (the subject of a blackboard post) |
| `MAX_TEXT` | 20,000 | Message body, `filestore_read_text` output |
| `MAX_ATTACHMENTS` | 20 | Attachments per message |
| `FILE_ID_RE` | `^f_[0-9a-f]{32}$` | File ids |
| `MAX_FILE_SIZE` | 25 MB | One stored file |
| `MAX_NAME` | 200 | Stored file name (longer names are shortened, keeping the extension) |
| `MAX_NOTE` | 1,000 | A stored file's note |
| `HUMAN` | `"human"` | The user's name as sender, receiver and author |

`check_agent_name()` and `check_channel_name()` raise `ValueError` for any
other name; `check_recipient()` accepts either. Subjects, topics,
bodies and texts are stripped and must not be empty. Every validation error is
a `ValueError`; the CLI shows it as `Error: …`.

Message ids are the first 12 hex characters of a UUID4; file
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

### Message states

Every message is in one of four states:

| State | Meaning |
|---|---|
| `unread` | Delivered; nobody took it yet |
| `processing` | Claimed by an owner (a worker instance) that is working on it |
| `read` | Read, claimed without an owner, or finished by its owner (`ack`) |
| `failed` | Not answered: `fail`, or recovered from an owner that died |

### `Mailbox(agent, store=None)`

`Mailbox` checks names and texts and builds messages; a
[`MailboxStore`](#mail-storage) keeps them. `store` defaults to
`default_mailbox_store()`.

| Method | Does |
|---|---|
| `Mailbox.send(sender, to, subject, body, reply_to=None, attachments=None, store=None)` | Static. Validates, then delivers the message as `unread` to the receiving agent, or posts it if `to` is a channel (see [Channels](#channels)). `attachments` are file ids (see [Attachments](#attachments)). Returns the message |
| `list(include_read=False, preview_chars=0)` | Headers (`id`, `ts`, `from`, `subject`, `reply_to`, `read`, `failed`, `attachments` (a count)) of unread messages, oldest first, optionally with read and failed ones and a body preview |
| `read(message_id)` | The full message in any state; an unread one becomes `read`. Raises `ValueError` for an invalid or unknown id |
| `status(message_id)` | `(state, owner)`; `owner` is set while the message is `processing` |
| `claim_next(owner=None)` | Takes the oldest unread message and returns it, or `None` if there is none. Without `owner` it becomes `read` at once; with `owner` it becomes `processing` (a lease, see below) |
| `ack(message_id, owner)` | Marks a message held by `owner` `read`; `False` if `owner` doesn't hold it |
| `fail(message_id, owner)` | Marks a message held by `owner` `failed`; `False` if `owner` doesn't hold it |
| `owners()` | The owners that hold messages |
| `recover(is_alive, was_answered=None)` | For every owner where `is_alive(owner)` is false, marks its messages `read` if `was_answered(message)` is true, else `failed`. Returns `(owner, message, answered)` triples |
| `find_reply(message_id)` | A message in this inbox (any state) whose `reply_to` is `message_id`, or `None` |

`list(include_read=True)` returns `unread`, `read` and `failed` messages (not
`processing` ones); headers have `read` and `failed` flags.

`Mailbox.send` doesn't check that the receiver exists; callers do (see
`known_agents()`).

### Mail storage

`MailboxStore` (`geenii.ibc.mailstore`) is the storage protocol
(`typing.Protocol`, runtime-checkable). A new backend implements it and is
passed as `store=`, or returned by `default_mailbox_store()`. Its methods
take the recipient (an agent or a channel) and work on whole messages.

Direct mail:

| Method | Does |
|---|---|
| `deliver(message)` | Stores a new message as `unread` under `message["to"]` |
| `messages(agent, states=("unread",))` | `(message, state, owner)` triples in those states, oldest first |
| `get(agent, message_id)` | `(message, state, owner)` or `None` |
| `mark_read(agent, message_id)` | `unread` → `read`; `False` if it wasn't unread |
| `claim_next(agent, owner=None)` | Oldest `unread` → `processing` under `owner`, or → `read` without one; the message or `None` |
| `finish(agent, message_id, owner, state)` | `processing` held by `owner` → `read` or `failed`; `False` if `owner` doesn't hold it |
| `owners(agent)` | Owners with `processing` messages |
| `find_reply(agent, message_id)` | A message whose `reply_to` is `message_id`, or `None` |
| `pending_attachment_ids()` | File ids attached to `unread` or `processing` messages of any agent (used by `files gc`) |

Channels:

| Method | Does |
|---|---|
| `post(message)` | Stores a post (state `posted`) in the channel `message["to"]`; returns its cursor |
| `channel_messages(channel, after=None, subject=None, sender=None, limit=20)` | `(cursor, message)` pairs, oldest first: with `after`, the first `limit` posts after that cursor; without, the latest `limit`. `subject` matches case-insensitively |
| `channel_end(channel)` | The cursor of the newest post (`0` if none) |
| `subjects(channel)` | `{subject: number of posts}`, in order of first use |
| `channels()` | `{channel: number of posts}` |
| `get_cursor(channel, agent)` | The cursor of the last post `agent` has seen, or `None` if it never read the channel |
| `advance_cursor(channel, agent, cursor)` | Moves the agent's cursor forward; never backwards |

Every state change must be atomic, and the store must be safe from several
threads and processes: each message is claimed once, only its owner can
finish it, and a cursor never moves backwards.

Cursors are opaque, increasing integers, not timestamps: two posts in the
same second would tie, and `ts` comes from the sender's clock.

`SqliteMailboxStore(path=None)` is the default, in `GEENII_HOME/mail.db`
(resolved on every call, so a changed `GEENII_HOME` takes effect). It has two
tables:

- `messages`: `seq` (insert order; also the channel cursor), `id`,
  `recipient` (agent or channel), `reply_to`, `state`, `owner`, `updated_at`,
  and `data`, the message as JSON.
- `channel_cursors`: `(channel, agent)` → `last_seq`. Advancing is an upsert
  with `MAX(last_seq, new)`.

`seq` is an `AUTOINCREMENT` key, and SQLite lets only one writer in at a
time, so a post with a lower `seq` never commits after one with a higher
`seq`: a reader that has seen cursor N never misses a post below it.

A new database gets its tables on first use; `PRAGMA user_version`
(`SCHEMA_VERSION`) marks it as set up. There are no migrations: a database
from an older schema must be deleted.
Each call opens its own connection, so one store can be shared by threads.
The database runs in WAL mode with a busy timeout (30 s), so readers don't
block writers. `claim_next` selects and updates in one `BEGIN IMMEDIATE`
transaction; `mark_read` and `finish` are single conditional `UPDATE`s whose
row count says whether they won.

### Attachments

`Mailbox.send(..., attachments=[file_id, …])` attaches files of the
[file store](#file-store). After the message itself has passed validation,
it:

1. drops duplicate ids and rejects more than `MAX_ATTACHMENTS`;
2. looks up every id first, so an unknown id fails the whole send and nothing
   is shared;
3. adds the receiver to each file's `shared_with`, so the files show in its
   filebox (not for channel posts: their files are readable by id, but show
   in no filebox);
4. stores `{id, name, size, mime}` per file in the message.

The files themselves are not copied into the inbox.

### Leases

A worker claims with its instance id as `owner` (`OWNER_RE`:
`^[A-Za-z0-9_][A-Za-z0-9._-]{0,127}$`), so a message it works on is
`processing`, held by that owner. When it is done it calls `ack()` (answered,
`read`) or `fail()` (not answered, `failed`). If the owner dies in between,
`recover()` takes the message over: messages are never put back in the
inbox, so none is handled twice. Every state change is atomic, so workers
recovering at the same time each take a message at most once. See
[workers](workers.md#delivery) for how workers decide that an owner is dead.

### `known_agents()`

Returns `{name: description}` for every agent in the global agent registry
(`g.get_agent_registry()`, see [agents](agents.md#agent-registry)) plus
`human`. The CLI and the `agentmail_send` tool use it to reject unknown receivers;
[workers](workers.md) only reply to senders in it.

`known_channels()` returns `{name: description}` for `@blackboard` plus every
channel that has posts. The `agentmail_send` tool only posts to these, so a typo
doesn't create a channel; `geenii worker send` posts to any valid channel
name.

## Channels

A message whose recipient starts with `@` is a channel post. Channels are
open: anyone can post and read, and a channel exists once it has a post.
Posts have no per-reader state; instead each agent has a **cursor** per
channel, the position of the last post it has seen. Workers never handle
posts: `claim_next()` only takes direct mail, so a post doesn't wake every
worker.

### `Channel(name, store=None)`

| Method | Does |
|---|---|
| `post(sender, subject, body, reply_to=None, attachments=None)` | `Mailbox.send()` to the channel. Returns the message |
| `read(topic=None, limit=20, author=None)` | The latest `limit` posts, oldest first, optionally one subject (case-insensitive) or author. Moves no cursor |
| `read_new(agent, limit=20)` | Posts `agent` hasn't seen, oldest first, without its own; moves its cursor past them. More than `limit` new posts come in later calls |
| `topics()` | `{subject: number of posts}` |

The first `read_new()` of an agent in a channel returns nothing and starts
its cursor at the newest post, so a new reader isn't flooded with history;
`read()` shows older posts.

### Blackboard

`Blackboard(store=None)` is `Channel("@blackboard")`. Its
`post(author, topic, text)` checks the topic against `MAX_TOPIC` and posts it
as the subject. A post is an ordinary message:

```json
{"id": "c5bb31850e1b", "ts": "2026-11-20T09:31:00+00:00", "from": "human", "to": "@blackboard", "subject": "monthly-report", "body": "Numbers for October are in.", "reply_to": null}
```

## Tools for agents

`comms_tools(agent_name)` returns six `PythonFunctionTool`s bound to one
agent, which always acts as itself (`COMMS_TOOL_NAMES`):

| Tool | Does |
|---|---|
| `blackboard_post(topic, text)` | Post an entry as the agent |
| `blackboard_read(topic="", limit=20, new_only=false)` | Latest entries; with `new_only`, the entries posted since the agent last checked (`read_new()`; `topic` is ignored). With none, also the list of topics |
| `agentmail_send(to, subject, body, reply_to="", attachments=[])` | Send mail, or post to a channel in `known_channels()`, optionally with file ids attached; rejects unknown receivers and mail to itself |
| `agentmail_check_inbox()` | All unread messages in full; they are marked read |
| `agentmail_read(message_id)` | One message again, read or not |
| `agentmail_contacts()` | The other agents, `human` and the known channels, with descriptions |

`init_agent()` registers the ones an agent spec lists in `tools`, bound to
that agent (`_register_ibc_tools()` in `geenii/g.py`); the same goes for the
[file tools](#file-tools-for-agents). An agent whose name isn't a valid
`AGENT_NAME_RE` name gets none of them, with a warning in the log.

```markdown
---
name: research
tools: [agentmail_send, agentmail_check_inbox, filestore_upload, filestore_download, filestore_read_text]
---
```

## File store

Agents share files through one store of immutable files, each referenced by
an id. A file is never changed after upload: a new version is a new upload
with a new id, so an id in a message always means the same content and
readers need no locks.

### Layout

This is the layout of `LocalFileStorage`, the default
[storage adapter](#file-storage):

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

An upload streams into `.tmp-<id>/`, writes `meta.json`, then renames the
folder into place. `FileStore` counts the size and hashes on the way; a file
over `MAX_FILE_SIZE` stops the copy and the temp folder is removed. A delete
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

### `FileStore(root=None, storage=None)`

`storage` is the [storage adapter](#file-storage) (default:
`default_file_storage()`); `root` is a shortcut for `LocalFileStorage(root)`.

| Method | Does |
|---|---|
| `put(owner, src, name=None, note="")` | Copies the file `src` into the store under `name` (default: its own). Returns the metadata |
| `put_bytes(owner, data, name, note="")`, `put_text(owner, name, text, note="")` | The same from memory (text as UTF-8) |
| `info(file_id)` | The metadata. `ValueError` for an invalid, unknown or damaged id |
| `exists(file_id)` | `True` if the file is there; `False` also for invalid ids |
| `open(file_id)`, `read_bytes(file_id)` | The file's bytes as a binary stream (close it), or all of them |
| `read_text(file_id, limit=MAX_TEXT)` | `(text, truncated)`. Decodes UTF-8; `ValueError` for binary files |
| `copy_to(file_id, dest, overwrite=False)` | Copies the file to `dest`, a file path or a folder (then under the file's name). `ValueError` if the target exists and `overwrite` is false |
| `list(agent=None)` | Metadata of all files, newest first, or only `agent`'s filebox. Damaged files are skipped |
| `share(file_id, agents)` | Adds agents to `shared_with` (never the owner, never twice), through the adapter's atomic `update_meta` |
| `delete(file_id, by=None)` | Deletes the file. `by`, if given, must be the owner; `None` deletes as admin |
| `gc(older_than, keep=None)` | Deletes files older than `older_than` (a `timedelta`), except `keep` and files attached to mail that is unread or claimed by a worker (`attached_to_pending_mail()`). Also has the adapter remove leftovers of interrupted uploads and deletes that old (`purge_incomplete`). Returns the deleted ids |

`clean_name()` keeps only the last path segment of a name and drops control
characters, so a name like `../../etc/passwd` is stored as `passwd`. The
MIME type is guessed from the name.

### File storage

`FileStorageAdapter` (`geenii.storage.filestorage`) is the storage protocol
(`typing.Protocol`, runtime-checkable), so files can later live in S3, on an
FTP or WebDAV server and so on. `FileStore` does all checks (owner, name,
size, id), counts and hashes uploads and builds the metadata; an adapter only
keeps a file's bytes and its metadata dict under the id. Ids are validated
before they reach the adapter, so it can use them as keys or path segments.

| Method | Does |
|---|---|
| `create(file_id, data, meta)` | Reads the stream `data` to the end, then calls `meta()` for the metadata and stores both. The file appears complete or not at all; on an error nothing is left and the error propagates. Returns the metadata |
| `read_meta(file_id)` | The metadata |
| `update_meta(file_id, change)` | Calls `change(meta)` and stores what it returns (`None`: no change), atomically with respect to other updates. Returns the stored metadata |
| `open(file_id)` | The bytes as a readable binary stream |
| `delete(file_id)` | Removes bytes and metadata, so readers see the whole file or none |
| `ids()` | The ids of all complete files |
| `purge_incomplete(before)` | Removes leftovers of uploads and deletes interrupted before `before` |

A missing file raises `FileNotFoundError`, unreadable metadata `ValueError`;
`FileStore` turns both into `ValueError`s with a message for the agent.

`LocalFileStorage(root=None)` is the only adapter so far: the
[layout](#layout) above, in `GEENII_HOME/files` (resolved on every call).
`update_meta` holds an `fcntl` lock on `.lock`, so it is safe across
processes on one machine. `default_file_storage()` returns it.

### File tools for agents

`files_tools(agent_name)` returns six tools bound to one agent
(`FILE_TOOL_NAMES`). Uploads are owned by that agent. Paths are relative to
the agent's working folder (`ctx.cwd`) and must pass the same check as the
`read` and `write` tools (`is_file_in_allowed_dirs()`: the agent's working
folder, `GEENII_WORKING_DIR` or the user settings' `allowed_dirs`; symlinks
are resolved first).

| Tool | Does |
|---|---|
| `filestore_upload(path, note="")` | Uploads a file from the working folder; returns `{id, name, size, mime, owner, created_at, note}` |
| `filestore_download(file_id, path="", overwrite=false)` | Copies a stored file into the working folder, by default under its own name; refuses to overwrite unless `overwrite` |
| `filestore_list()` | The agent's filebox; each entry has `shared: true` if another agent owns it |
| `filestore_info(file_id)` | Metadata including `sha256` and `shared_with`, without the content |
| `filestore_save_text(name, text, note="")` | Stores text as a new file, for agents without file system tools |
| `filestore_read_text(file_id)` | Up to `MAX_TEXT` characters of a text file, with a `truncated` note if there is more |

Errors (unknown id, path not allowed, binary file, …) come back as tool
errors (`is_error`), not exceptions. `init_agent()` registers the ones a
spec lists in `tools`, as for the [mail tools](#tools-for-agents).

## Formatting helpers

`format_inbox(headers)` and `format_blackboard(entries)` render headers and
entries as plain text for the CLI (`No unread mail.`, `The blackboard is
empty.` when empty); `format_inbox` adds `[n files]` for messages with
attachments. In `filestore.py`, `format_attachments(attachments)` renders one
`- name (id, size)` line per file, and `format_size()` a byte count.

## Known limitations

- **No retry:** a message whose worker crashes ends as `failed` and is not
  handled again; see [workers](workers.md#delivery).
- **No automatic cleanup:** read and failed mail and channel posts grow
  forever.
- **Open channels:** there are no members or private channels; every agent
  can read and post to every channel. Stored files are only removed by `geenii worker files gc` or
  `rm`.
- **No deduplication or quotas:** uploading the same content twice stores it
  twice, and only the per-file size is limited.
- **No access control:** any process that can write `GEENII_HOME` can send
  mail as any name, post as any author, or read any stored file. The sender
  name is not authenticated (see [Access](#access)).
- **Polling only:** there is no notification; readers query the inbox or
  their channel cursor.
- **One machine:** SQLite locking doesn't work reliably on network file
  systems, so don't share `GEENII_HOME` between machines.
