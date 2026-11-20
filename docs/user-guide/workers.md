# Workers and Agent Mail

A **worker** is an agent that runs unattended: it waits for messages in its
inbox and answers them. Agents and you talk to each other through **agent
mail** (one inbox per agent), a shared **blackboard** (notes under a
topic) and a shared **file store** (files referenced by id). Together these
are geenii's inter-bot communication (IBC).

Everything is stored as plain files in `GEENII_HOME` (default `~/.geenii`), so
it works without the daemon or the server and survives restarts.

## Quick start

Start a worker for an agent (here `research`) in one terminal:

```bash
geenii worker serve research
```

Ask it something from another terminal:

```bash
geenii worker ask research "Summarize the latest papers on RAG evaluation"
```

`ask` mails the question to `research` and waits for the answer (up to five
minutes by default). Instead, you can send mail and read the answer later:

```bash
geenii worker send research "rag papers" "Summarize the latest papers on RAG evaluation"
geenii worker inbox            # your inbox: 'human'
geenii worker inbox --read <ID>
```

## How a worker answers

For each message, the worker:

1. takes the oldest unread message from the agent's inbox,
2. creates a **fresh agent instance**: nothing is remembered between messages,
3. gives it the message as the prompt: `Message from agent '<sender>' (subject: <subject>):` followed by the body
   and, if files are attached, a list of them (name, id, size),
4. mails the agent's final answer back to the sender, with the subject
   `Re: <subject>`.

If the agent fails, the sender gets `Error while handling your message: …`
instead. The worker carries on with the next message.

A worker does **not** answer:

- a message that is itself a reply, so two agents can't keep answering each
  other's answers,
- a message from itself,
- a message from a sender that is neither a configured agent nor `human`.

## Tool approval

When you chat with an agent, you can approve its tool calls. A worker has
nobody to ask, so `--approve` decides for every tool call:

| Policy | Effect |
|---|---|
| `none` (default) | Every tool call is denied; the agent can only answer from the model |
| `all` | Every tool call is allowed |
| `tool1,tool2` | Only these tools are allowed |

```bash
geenii worker serve web --approve mcp__duckduckgo__search,mcp__duckduckgo__fetch_content
```

The policy can also come from the `GEENII_APPROVE` environment variable.
Mail can come from any agent, so allow only the tools a worker needs.

## Several workers

You can start several workers for the same agent, also on several machines
that share `GEENII_HOME`. Each message is taken by exactly one of them. Workers
for different agents can mail each other: an agent's answer to a message from
another agent goes to that agent's inbox.

`geenii worker list` shows the workers with their status (`idle`, or `busy`
with how long they have been working on the current message). A worker that
hasn't reported for 60 seconds is shown as `gone?`; it was probably killed.

To run a worker in the background, use the
[supervisor](../cli-reference/supervisor.md):

```bash
geenii supervisor add research-worker -- geenii worker serve research
```

Or let the [scheduler](scheduler.md) process the inbox at intervals with
`geenii worker serve research --once`, which exits when the inbox is empty.

## The blackboard

The blackboard is a shared list of notes under topics, which you and the
agents can read. Use it for results that several agents or people need.

```bash
geenii worker post monthly-report "Numbers for October are in."
geenii worker blackboard                      # latest 20 entries + all topics
geenii worker blackboard --topic monthly-report
```

## Sharing files

Agents and you can share files through the file store. Every file gets an
id such as `f_3f9c0d…`; you pass the id around instead of the file. Stored
files never change: a new version is a new upload with a new id.

```bash
geenii worker files put data.csv --note "October numbers"   # prints the id
geenii worker send research "numbers" "Summarize the attached file" -a f_3f9c0d…
geenii worker send research "numbers" "Summarize this" -a ./data.csv   # upload and attach in one go
geenii worker files list research          # the files research has, uploaded or received
geenii worker files get f_3f9c0d… ./out/   # save a file
```

Attaching a file to a message puts it in the receiver's **filebox**: the
files it uploaded plus the ones it received. The worker lists the attached
files in the prompt, so the agent can open them.

To let an agent work with files, list the file tools in its spec, for
example:

```markdown
---
name: research
tools: [file_read_text, file_download, file_upload, file_save_text, file_list, send_mail]
---
```

| Tool | Does |
|---|---|
| `file_upload` | Stores a file from the agent's working folder and returns its id |
| `file_download` | Copies a stored file into the agent's working folder |
| `file_save_text` | Stores text as a new file (no file system access needed) |
| `file_read_text` | Reads a stored text file (up to 20,000 characters) |
| `file_list` | Lists the agent's filebox |
| `file_info` | Shows a file's name, size, type, owner and note |

`file_upload` and `file_download` only work inside the folders the `read`
and `write` tools may use: the agent's working folder, the current project
and the `allowed_dirs` in your settings. For a worker, also allow the tools
with `--approve`, for example `--approve file_read_text,file_save_text`.

Anyone who knows a file's id can read it; ids are long and random, so they
can't be guessed. Only the owner (or you, through the CLI) can delete a file.
Files are kept until you delete them:

```bash
geenii worker files rm f_3f9c0d…
geenii worker files gc --older-than 30   # days; keeps files attached to unread mail
```

## Limits

- Agent names used for mail must be lowercase letters, digits, `-` and `_`
  (up to 64 characters). Agents with other names can't send or receive mail.
- A subject can have up to 200 characters, a body or blackboard entry up to
  20,000. Longer answers are cut off with `... [truncated]`.
- If a worker crashes or is killed while working on a message, the next
  worker of that agent moves the message to the agent's `failed` folder and
  tells the sender that it wasn't answered. It is not retried: send it again.
  `geenii worker inbox <agent> --all` lists failed messages.
- A stored file can be up to 25 MB, and a message can have up to 20
  attachments.
- Agents only get the mail, blackboard and file tools that their spec lists
  in `tools` (see [IBC internals](../developer-guide/ibc.md#tools-for-agents)).
  Agents whose names don't fit the rules above can't use them.

See the [worker CLI reference](../cli-reference/worker.md) for all commands
and options.
