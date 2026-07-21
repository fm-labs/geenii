# Geenii Documentation

A minimal but powerful orchestration framework for agentic applications.

Geenii takes a **local-first, privacy-first** approach to AI workloads: a
unified API over local and remote LLM providers, agents defined as plain
markdown files, tool calling (including MCP servers), reusable skills, and a
scheduler for autonomous runs — all self-hosted, driven from the CLI.

## Quick orientation

```bash
geenii info                          # providers, models, environment
geenii agent "Hello, who are you?"   # run the default agent
geenii agents list                   # what agents are configured
geenii tools list                    # what tools are available
geenii skills list                   # what skills are installed
```

Agents, skills, and MCP servers are configured in the `.geenii/` directory of
your working directory — see [Configuration](user-guide/configuration.md) for
the layout.

## User Guide

How to set up, configure, and use Geenii.

- **[Installation](user-guide/installation.md)** — prerequisites, provider
  setup, and verification.
- **[Configuration](user-guide/configuration.md)** — the `.geenii/` directory,
  environment variables, `geenii.json`, `mcp.json`, logs, and caches.
- **[Agents](user-guide/agents.md)** — defining agents in markdown, AgentSpec
  fields, running and listing agents.
- **[Scheduler](user-guide/scheduler.md)** — running agents on a cron schedule.
- **[Docker](user-guide/docker.md)** — running Geenii in Docker.

## CLI Reference

Every command and option, one page per subcommand.

- **[CLI Reference Index](cli-reference/index.md)** — global options, full
  command tree, and links to each subcommand page.

## Developer Guide

Internals for contributors and library consumers.

- **[Architecture](developer-guide/architecture.md)** — components, package
  layout, request lifecycle, caching, and concurrency model.
- **[Agents](developer-guide/agents.md)** — agent runtime, task queue, HITL
  controllers, and programmatic API.
- **[Messages & Content Parts](developer-guide/messages.md)** — internal
  message formats, content part types, and per-provider wire mappings.
- **[Providers & Models](developer-guide/providers.md)** — provider interfaces,
  implemented providers, request/response models, and how to add a provider.
- **[Tools](developer-guide/tools.md)** — tool types, built-ins, MCP server
  tools, and registering your own.
- **[Skills](developer-guide/skills.md)** — the `SKILL.md` format, discovery,
  selection, and how skill instructions reach the model.
- **[Sandbox](developer-guide/sandbox.md)** — Docker-based code isolation,
  security model, SandboxTool API.
- **[Memory](developer-guide/memory.md)** — ChatMemory abstraction and
  persistence implementations.
- **[Building](developer-guide/building.md)** — dev setup, linting, testing,
  build targets (wheel, PyInstaller, Docker), CI/CD, and releases.
