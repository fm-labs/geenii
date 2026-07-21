# Suggested Improvements

Findings from a code review of the `geenii` codebase (v0.3.1). Grouped by category,
roughly ordered by priority within each group. File references point at the relevant code.

## 1. Correctness bugs

- [x] **Tool-call loop drops parallel tool calls** — `LLMTask.execute()` recomputes
  `tool_call_contents` from the latest response and only pops the first one; if the model
  returns multiple tool calls in a single response, all but the first are silently discarded
  (`src/geenii/agent/tasks.py`, ~line 122-136). Execute all tool calls from a response before
  re-generating.
- [x] **Redundant follow-up completion after tool calls** — after the in-loop re-generation,
  `LLMTask` enqueues *another* full `LLMTask` ("Based on the tool results, continue...")
  (`src/geenii/agent/tasks.py`, ~line 171-177). This costs an extra LLM round-trip per
  tool-using prompt and can produce duplicated answers. The in-loop regeneration already
  covers this.
- [x] **Off-by-one in tool-call limit** — `if tools_called > self.MAX_TOOL_CALLS` allows
  `MAX_TOOL_CALLS + 1` calls (`src/geenii/agent/tasks.py`, ~line 129).
- [x] **`ComputerTool.run_subprocess` crashes when `env` is None** — `invoke()` guards with
  `env or {}` for `expand_vars` but passes the raw `env` to `run_subprocess`, where
  `_env.update(env)` raises `TypeError` on None (`src/geenii/tool/computer.py`, ~line 45/57).
- [x] **`PythonCliTool` wipes the subprocess environment** — passes the tool env dict as the
  *entire* environment (`subprocess.run(..., env=env)`), losing `PATH`, `HOME`, etc.
  Inconsistent with `ComputerTool`, which merges into `os.environ`
  (`src/geenii/tool/python.py`, ~line 79).
- [x] **`ToolRegistry.invoke()` signature mismatch** — calls `tool.invoke(args=args, **kwargs)`
  but `Tool.invoke` requires `env` positionally; any call through the registry without an
  explicit `env` kwarg raises `TypeError` (`src/geenii/tool/registry.py`, ~line 135-139).
  Give `env` a default of `None` in the `Tool.invoke` signature (and fix the None handling above).
- [x] **`SkillSpec.from_path` produces `['']` for missing `allowed-tools`** —
  `skill_header.get("allowed-tools", "").split(" ")` yields a list with one empty string
  (`src/geenii/skills.py`, ~line 48).
- [x] **User message appended to history *after* the assistant reply on first turn** — in
  `LLMTask`, the user prompt is appended to `message_history` only after the completion
  returns, but the request itself uses the prior history snapshot; interleaving with queued
  tasks can order history incorrectly (`src/geenii/agent/tasks.py`, ~line 104-114).
- [x] **`ToolFilterTask` system prompt talks about "agents"** — should say "tools"
  (`src/geenii/agent/tasks.py`, ~line 232-244).
- [x] **`PlanTask` prompt template references `{{{tools_list}}}` but the template only contains
  `{{{skills_list}}}`** — the `_build_tools_list()` output is never injected; also the numbered
  workflow skips step 3 (`src/geenii/agent/tasks.py`, ~line 541-563).
- [x] **`ChatCompletionRequest.messages` may be None** — Ollama provider does
  `len(request.messages)` and iterates without a None guard
  (`src/geenii/provider/ollama/provider.py`, ~line 190-201).
- [x] **`BaseCompletionResponse.model_result: dict = None`** — non-optional type annotation with
  a None default; should be `dict | None = None` (`src/geenii/datamodels.py`, ~line 74).

## 2. Packaging & distribution

- [x] **Broken console-script entry point** — `pyproject.toml` declares
  `geenii-cli = "cli:main"`, but the hatch wheel config only packages `src/geenii`, so the
  top-level `src/cli.py` module is not installed and the script fails after `pip install`.
  Move `src/cli.py` into the package (e.g. `geenii/cli/main.py`) and update the entry point.
- [x] **Command name mismatch** — README consistently uses `geenii` as the command, the entry
  point is `geenii-cli`. Pick one (suggest `geenii`).
- [x] **Stale `[tool.setuptools.packages.find]` section** — the build backend is hatchling;
  the setuptools table is dead config (`pyproject.toml`).
- [x] **`redis` and `testcontainers` are dev-only deps but `utils/redis.py` and
  `utils/mongodb.py` import them at module level** — importing those modules in a
  production install fails. Either make them optional extras (`geenii[redis]`) or guard imports.

## 3. Features & architecture

- [x] **Implement the Anthropic provider** — `anthropic` is already a runtime dependency and the
  README advertises Claude support, but `get_ai_provider("anthropic")` raises
  `NotImplementedError` (`src/geenii/ai.py`, ~line 128). The Ollama provider is a good template.
- [x] **Dynamic provider discovery** — `get_ai_provider()` has the dynamic-import version
  commented out and hardcodes an if/elif chain; each provider module already exposes
  `ai_provider_class`. Finish the plugin-style loading and drop `SUPPORTED_PROVIDERS`
  hardcoding (`src/geenii/ai.py`).
- [x] **Reuse MCP client connections** — every `McpTool.invoke()` creates a fresh `McpClient`
  and a new connection/handshake per call (`src/geenii/tool/mcp.py`). Cache clients per server
  (and reuse the connection across `list_tools` / `call_tool`).
- [ ] **Streaming support** — `stream` is plumbed through the request models but no provider
  implements it; the CLI would benefit most. Consider an `AsyncGenerator`-based provider API.
- [ ] **Message-history management** — history is capped at a hardcoded `[-10:]` slice in
  `LLMTask`; the `ChatMemory` abstraction exists (`src/geenii/memory.py`) but `BaseAgent`
  never uses it. Wire memory into the agent and make the window/token budget configurable.
- [ ] **`--conv-id` / `--continue` CLI options are dead** — accepted but commented out /
  unimplemented (`src/geenii/cli/agent.py`). Implement conversation persistence via
  `FileChatMemory` or remove the flags.
- [ ] **`model_parameters`, `developer_prompt`, `output_format` overrides set attributes that
  `BaseAgent` doesn't define/use** — e.g. `gbot.model_parameters = ...` in the CLI has no
  effect on requests (`src/geenii/cli/agent.py`, `src/geenii/agent/base_agent.py`).
- [ ] **Duplicate tool definitions** — `bash`/`python` exist both as
  `ComputerTool`s in `src/geenii/tools.py` and as decorated functions in
  `src/geenii/core/tools.py` (separate registry). Consolidate into one module; note
  `python` is currently just a shell executor with a misleading name.
- [x] **Duplicate helpers** — `split_model()` and `map_model_id()` are identical
  (`src/geenii/ai.py`, ~line 68-95). Keep one.
- [ ] **`FindBestSkillTask` runs before every prompt** — even for agents without skills it costs
  a queue slot; with 2+ skills it costs an extra LLM call per prompt. Consider selecting once
  per conversation, or only when the skill set changes.

## 4. Code quality

- [ ] **Replace `print()` with `logging` throughout** — providers dump full message payloads and
  raw model responses to stdout (`src/geenii/provider/ollama/provider.py` ~line 191/205/239,
  `src/geenii/tool/computer.py` ~line 54, `src/geenii/mcp.py`, `src/geenii/ai.py`, ...).
  This pollutes CLI output and can leak prompt/tool data.
- [ ] **Remove dead/commented-out code** — large commented blocks in `ai.py`, `tools.py`,
  `skills.py`, `memory.py` (SqliteChatMemory), `config.py`, `agent/tasks.py` (FinalizeTask,
  AnonymousTask), `src/geenii/example_bots.py`, and the leftover `src/xsandbox.py`.
- [x] **Consistent naming: "HITL" vs "HIDL"** — the module is `hitl.py` but variables/docstrings
  say `hidl` / "H.I.D.L" (`src/geenii/agent/base_agent.py`, `src/geenii/hitl.py`).
- [x] **Typos** — `provier` (`src/geenii/g.py` ~line 110), "compoter tools" (README),
  "Tipp" (README), CLI group docstring "AI agents, tools, and agents" (`src/cli.py`).
- [ ] **Make defaults configurable via env** — `DEFAULT_COMPLETION_MODEL` etc. are hardcoded in
  `src/geenii/config.py`; support `GEENII_DEFAULT_MODEL` and friends.
- [x] **Add `ruff` (lint + format) config** and run it over the codebase; wire into CI.
- [ ] **Type-checking** — annotations are inconsistent (`any` instead of `Any` in
  `src/geenii/mcp.py` ~line 148/158); consider mypy/pyright in CI.
- [x] **Stray debug output in `PlanTask.execute`** — the `print("***"...)` block dumping the
  system prompt (`src/geenii/agent/tasks.py`, ~line 593-597).
- [x] **Logger side effects at import time** — `logging.basicConfig()` called at module import in
  `scheduler.py` and `supervisor.py`; rotating file handlers added at import in several
  modules, which duplicates handlers under re-import and makes the library noisy when embedded.

## 5. Documentation

- [x] **Sync README with the actual CLI** — README documents `geenii mcp ...` and
  `geenii models ...` command groups that are not registered in `src/cli.py`; the two
  `geenii --help` blocks contradict each other (one shows the runner, one the group);
  `-c/--continue` vs the actual `-i/--interactive` flag.
- [x] **README mentions WebUI / Daemon / REST API / chat server** — that code was moved to a
  separate repo (per git history). Either link the server repo or trim these sections.
- [x] **Document the `.geenii` directory layout** in one place (agents/, skills/, mcp.json,
  geenii.json, scheduler.json, .env) — `.geeniidev/` in this repo is a good live example.
- [x] **Docstring drift** — e.g. `init_agent_by_name()` says "Load ... from a JSON file" but
  loads markdown (`src/geenii/g.py`, ~line 64).

## 6. Testing & CI

- [ ] **Refresh the test suite** — current tests (modelstore, memory) are outdated; there are no
  tests for the core value paths: tool registry, tool-call loop, agent/skill selection,
  provider message mapping (`model_messages_to_ollama_format` is a prime unit-test target).
- [x] **Add a CI test workflow** — `.github/workflows/` only has reposcan and publish jobs;
  add lint + pytest on PRs.
- [x] **Fake/stub provider for tests** — a deterministic `AIChatCompletionProvider` would allow
  testing the whole agent loop without network/Ollama.

## 7. Security & safety

- [ ] **`bash` runs arbitrary shell commands with no policy** — the allowlist idea is
  sketched but commented out (`src/geenii/core/tools.py`). Implement a tool-usage policy
  (allowlist/denylist, working-dir confinement) and default the HITL controller to a
  confirming implementation in interactive CLI runs (`CliHumanInTheLoopController` exists but
  is commented out in `src/geenii/cli/cli_runner.py`).
- [ ] **Docker sandbox exists but is unused** — `src/geenii/sandbox.py` /
  `run_docker_sandbox_python` could back `python` for real isolation.
- [ ] **AI request/response logs may contain sensitive data** — `_ai_log()` writes full requests
  (incl. system prompts, tool results) to `CACHE_DIR/logs`; make this opt-in or redact.
- [ ] **Skill install from URLs** — README promises `skills install <url>`; when implemented,
  validate sources and require confirmation (supply-chain risk noted in README already).
