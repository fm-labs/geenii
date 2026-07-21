# g33n11

A local-first, privacy-first orchestration framework for AI agents.

Unified API over local and remote LLM providers, agents defined as plain
markdown files, tool calling (including MCP servers), reusable skills, and a
scheduler for autonomous runs — all self-hosted, driven from the CLI.

## Highlights

- **Multi-provider** — Ollama (local + cloud), OpenAI, Anthropic, and more
- **Tool calling** — Python functions, shell commands, and MCP server tools
- **Skills** — reusable instruction/script bundles in Anthropic's SKILL.md format
- **Sandboxed execution** — Docker-based isolation for untrusted code
- **Scheduler** — cron-style autonomous agent runs

## Quick start

```bash
brew tap fmlabs/formulas
brew install geenii
geenii info
geenii agent "Hello, who are you?"
```

Or run from source:

```bash
uv sync
uv run geenii info
uv run geenii agent "Hello, who are you?"
```

See the [installation guide](docs/user-guide/installation.md) for
prerequisites and provider setup.

## Cheat sheet

```bash
geenii agent "prompt"                # run the default agent
geenii agent -n my-agent -i "hi"     # named agent, interactive
geenii agents list                   # configured agents
geenii models list                   # available models
geenii tools list                    # registered tools
geenii skills list                   # installed skills
geenii mcp server list               # MCP servers
geenii scheduler start               # start the task scheduler
geenii pm serve                      # start the process manager
```

See the [Cheatsheet](docs/cheatsheet.md) for more commands.
See the [CLI reference](docs/cli-reference/index.md) for the full command tree.

## Docker

Run Geenii in a container with pre-installed skills and tools.
See the [Docker guide](docs/user-guide/docker.md).

## Documentation

- [User Guide](docs/user-guide/) — installation, configuration, agents,
  scheduler, Docker
- [CLI Reference](docs/cli-reference/index.md) — every command and option
- [Developer Guide](docs/developer-guide/) — architecture, internals,
  provider/tool APIs
