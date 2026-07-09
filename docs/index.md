# Geenii Documentation

A minimal but powerful orchestration framework for agentic applications.

Geenii takes a **local-first, privacy-first** approach to AI workloads: a
unified API over local and remote LLM providers, agents defined as plain
markdown files, tool calling (including MCP servers), reusable skills, and a
scheduler for autonomous runs — all self-hosted, driven from the CLI.

## Contents

Start here:

- **[Architecture](architecture.md)** — components, package layout, and the
  life of a prompt from CLI to model to tool call.
- **[Configuration](configuration.md)** — the `.geenii/` directory, environment
  variables, `geenii.json`, `mcp.json`, logs, and caches.

Core components:

- **[Agents](agents.md)** — defining agents in markdown, the task-queue
  runtime, routing/handoff, memory, and human-in-the-loop approval.
- **[Skills](skills.md)** — the `SKILL.md` format, discovery, selection, and
  how skill instructions and scripts reach the model.
- **[Tools](tools.md)** — tool types, built-ins, MCP server tools, registering
  your own, and how tool calling works.
- **[Providers & Models](providers.md)** — the `provider:model` addressing
  scheme, provider interfaces, what each provider supports, and how to add one.
- **[CLI Reference](cli.md)** — every command and option that exists today.
- **[Scheduler](scheduler.md)** — running agents on a cron schedule.

For contributors:

- **[Developer Guide](developer.md)** — running from sources, tests, tooling.

## Quick orientation

```bash
geenii info                          # providers, models, environment
geenii agent "Hello, who are you?"   # run the default agent
geenii agents list                   # what agents are configured
geenii tools list                    # what tools are available
geenii skills list                   # what skills are installed
```

Agents, skills, and MCP servers are configured in the `.geenii/` directory of
your working directory — see [configuration.md](configuration.md) for the
layout.
