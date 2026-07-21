# Architecture

Geenii is a CLI-first framework for running AI agents against local and remote LLMs.
It is organized around a small set of concepts:

| Concept | What it is | Details |
|---|---|---|
| **Provider** | Adapter for an LLM backend (Ollama, OpenAI, ...) | [providers.md](providers.md) |
| **Agent** | A named configuration (model + instructions + tools + skills) plus a runtime that processes prompts through a task queue | [agents.md](agents.md) |
| **Tool** | A callable the model can invoke: a Python function, a shell command, or an MCP server tool | [tools.md](tools.md) |
| **Sandbox** | Docker-based isolation for running untrusted code in a container with restricted capabilities and resource limits | [sandbox.md](sandbox.md) |
| **Skill** | A directory with a `SKILL.md` (Anthropic skill format) whose instructions are injected into the system prompt | [skills.md](skills.md) |
| **Scheduler** | Cron-style runner that executes tasks (typically agent runs) from a JSON config | [scheduler.md](scheduler.md) |

All user-facing configuration lives in a `.geenii/` directory; see [configuration.md](configuration.md).

## Package layout

```
src/
├── cli.py                  # Console entry point: builds the click command group
└── geenii/
    ├── config.py           # Env vars, paths, defaults; loads .geenii/.env at import
    ├── g.py                # Global wiring: registries, agent lookup, app info
    ├── ai.py               # Provider dispatch: model-id -> provider, completion helpers, usage logging
    ├── datamodels.py       # Pydantic request/response models (completion, chat, image, audio, MCP)
    ├── chat_models.py      # Message content parts (text, tool_call, json, ...) and wire messages
    ├── agents.py           # Concrete agent classes (Agent, RoutingAgent)
    ├── agent/
    │   ├── base.py         # BaseTask, default system prompt
    │   ├── base_agent.py   # BaseAgent: task queue, initialization, HITL hook
    │   ├── tasks.py        # LLMTask, ToolCallTask, FindBestSkillTask, FindBestAgentTask, HandoffTask, PlanTask
    │   └── registry.py     # AgentSpec (markdown frontmatter), AgentRegistry
    ├── tool/
    │   ├── common.py       # Tool base class + definition mappers (OpenAI/Ollama format)
    │   ├── registry.py     # ToolRegistry
    │   ├── python.py       # PythonFunctionTool, PythonCliTool
    │   ├── computer.py     # ComputerTool (shell), AppleScriptTool
    │   └── mcp.py          # McpTool (delegates to an MCP server)
    ├── tools.py            # Built-in tool registration + MCP server tool discovery
    ├── core/
    │   ├── tools.py        # Decorator-registered utility tools (file ops, notifications)
    │   └── tasks.py        # Functions runnable by the scheduler (run_proc, cleanup, ...)
    ├── skills.py           # SkillSpec, SkillRegistry, skill discovery paths
    ├── mcp.py              # MCP config file access + McpClient (fastmcp wrapper)
    ├── provider/
    │   ├── interfaces.py   # AIProvider + capability interfaces (completion, chat, image, TTS, STT)
    │   ├── ollama/         # Ollama (chat, tools, JSON output) — most complete
    │   ├── openai/         # OpenAI (chat, tools, images, transcription)
    │   ├── geenii/         # Placeholder self-provider
    │   ├── hf/ kokoro/ whisper/   # Experimental extras
    │   └── ...
    ├── memory.py           # ChatMemory implementations (in-memory, JSONL file)
    ├── hitl.py             # Human-in-the-loop controllers (auto-approve, file ticket, HTTP poll)
    ├── scheduler.py        # Cron scheduler (geenii-scheduler entry point)
    ├── supervisor.py       # Asyncio process supervisor with log bus (library, used by the server repo)
    ├── sandbox.py          # Docker sandbox helpers for running Python in a container
    ├── cli/                # click command groups (agent, agents, tools, skills, scheduler, info)
    ├── logs.py             # Logging setup, rotating file handlers
    └── utils/              # Cache (SQLite), JSON/TOML helpers, frontmatter parser, system report, ...
```

The web UI, REST API daemon, and chat server mentioned in the README live in a
separate repository; this repo contains the core library, CLI, and scheduler.

## Request lifecycle

What happens on `geenii agent -n my-agent "do something"`:

```
CLI (cli/agent.py)
 └─ init_agent_by_name(name)           g.py: find <name>.md in $GEENII_DIR/agents/,
 │                                     parse AgentSpec, build Agent with its
 │                                     tool/skill registries
 └─ CliAgentRunner.run(prompt)
     └─ agent.prompt(prompt)           BaseAgent: lazy _initialize() registers
         │                             built-in tools + all MCP server tools
         ├─ _handle_prompt(prompt)     Agent enqueues:
         │    1. FindBestSkillTask     LLM call selecting the best skill (skipped
         │                             for 0 skills, auto-picked for exactly 1)
         │    2. LLMTask               the main completion
         └─ _process_queue()           drains the queue (max 10 tasks per prompt),
              │                        yields ModelMessages to the caller
              └─ LLMTask.execute()
                   ├─ builds system prompt: agent instructions + context info
                   │  (context id, datetime) + selected-skill instructions
                   ├─ generate_chat_completion()      ai.py -> provider
                   ├─ for each tool call in the response:
                   │    ├─ ToolCallTask: HITL approval -> tool.invoke()
                   │    ├─ appends tool call + result to message history
                   │    └─ re-generates the completion with the tool result
                   │       (bounded by MAX_TOOL_CALLS = 5)
                   └─ if tools were called, enqueues one follow-up LLMTask
```

Key properties of the loop:

- **Everything is a task.** Agent behavior is composed from `BaseTask` subclasses
  that an agent enqueues; tasks may yield messages (streamed to the caller) or
  further tasks (re-enqueued). `BaseAgent.MAX_TASKS` (10) bounds one prompt cycle.
- **Tool execution is mediated.** Every tool call passes through the agent's
  `HumanInTheLoopController` before executing (default: auto-approve).
- **History is windowed.** Requests include the last 10 messages of the agent's
  in-memory history. The `ChatMemory` persistence layer exists but is not yet
  wired into `BaseAgent`.

## Provider dispatch

Models are addressed as `provider:model_name` (e.g. `ollama:qwen3:8b`,
`openai:gpt-4o-mini`). `geenii.ai` splits the ID, instantiates the provider,
and forwards the request. Each chat completion is assigned a `context_id`,
and requests/responses plus token usage are appended to JSONL logs under
`$GEENII_CACHE_DIR/logs/`.

## Caching and state

| What | Where | Notes |
|---|---|---|
| AI request/response log | `$GEENII_CACHE_DIR/logs/ai-YYYY-MM-DD.log` | Full JSONL dump of requests and responses |
| Usage log | `$GEENII_CACHE_DIR/logs/ai-usage-YYYY-MM.log` | Per-call token/duration stats |
| Component logs | `$GEENII_CACHE_DIR/logs/*.log` | Rotating file handlers (tools, scheduler, supervisor) |
| Function cache | SQLite via `@cached(ttl=...)` (`utils/cached.py`) | Used for model enumeration and MCP tool listings (1 h TTL); disable with `GEENII_CACHE_DISABLED=true` |
| Model catalogs | `$GEENII_CACHE_DIR/{ollama,openai}.models.json` | Snapshots written on model enumeration |

## Concurrency model

The agent runtime is asyncio-based. Blocking provider SDK calls are pushed to a
thread via `asyncio.to_thread`; sync tool handlers run in the default executor;
shell tools run `subprocess` in a worker thread. The CLI wraps everything in a
single `asyncio.run()`.
