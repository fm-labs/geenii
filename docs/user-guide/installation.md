# Installation

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Install via Homebrew

```bash
brew tap fmlabs/formulas
brew install geenii
geenii --version
```

## Install from source

```bash
git clone <repo-url>
cd geenii
uv sync
uv run geenii --version
```

## AI Providers

You need at least one AI provider configured.

### Remote providers

Set the appropriate API key as an environment variable (or in `.geenii/.env`):

| Provider | Environment variable |
|---|---|
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| Ollama Cloud | `OLLAMA_API_KEY` |
| OpenRouter | `OPENROUTER_API_KEY` (not yet implemented) |

### Local models (recommended)

For local inference, install [Ollama](https://ollama.com/download) and pull at
least one model:

```bash
ollama pull qwen3:8b
```

Ollama is detected automatically at `http://localhost:11434` (override with
`OLLAMA_HOST`).

## Container runtime (optional)

A container runtime enables sandboxed code execution and
[Docker-based deployment](docker.md).

- [Docker Desktop](https://www.docker.com/products/docker-desktop) (recommended)
- [Podman](https://podman.io/getting-started/installation) (experimental)

## Verify

```bash
geenii info       # shows version, providers, and system report
geenii models list
```
