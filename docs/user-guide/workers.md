# Workers and Agent Mail

A **worker** is an agent that runs unattended: it waits for messages in its
inbox and answers them. Agents and you talk to each other through **agent
mail** (one inbox per agent) and a shared **blackboard** (notes under a
topic). Together these are geenii's inter-bot communication (IBC).

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
3. gives it the message as the prompt: `Message from agent '<sender>' (subject: <subject>):` followed by the body,
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

## Limits

- Agent names used for mail must be lowercase letters, digits, `-` and `_`
  (up to 64 characters). Agents with other names can't send or receive mail.
- A subject can have up to 200 characters, a body or blackboard entry up to
  20,000. Longer answers are cut off with `... [truncated]`.
- If a worker crashes or is killed while working on a message, the next
  worker of that agent moves the message to the agent's `failed` folder and
  tells the sender that it wasn't answered. It is not retried: send it again.
  `geenii worker inbox <agent> --all` lists failed messages.
- Agents can't use mail and the blackboard from a normal chat yet: the mail
  tools exist (see [IBC internals](../developer-guide/ibc.md#tools-for-agents))
  but are not given to agents.

See the [worker CLI reference](../cli-reference/worker.md) for all commands
and options.
