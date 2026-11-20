# Tools

A tool is a named, schema-described callable that the model can invoke during a
chat completion. Tools are held in a `ToolRegistry` (`geenii/tool/registry.py`);
each agent owns its own registry, populated by `init_agent()` from the agent
spec (see [agents.md](agents.md#runtime-model)). Registering a name that is
already registered logs a warning and keeps the existing tool (it no longer
raises).

## Tool types

All tools subclass `Tool` (`geenii/tool/common.py`), which carries `name`,
`description`, and a JSON-Schema `input_schema` dict (renamed from
`parameters`; the constructor keyword changed too), and implements a
synchronous `invoke(args, env, *, ctx: ToolCallContext) -> ToolCallResult`.

`ToolCallContext` (`geenii/tool/common.py`) is a dataclass with the call's
context; `invoke_tool()` builds it from its `cwd` argument:

| Field | Type | Meaning |
|---|---|---|
| `cwd` | `str` | Working directory of the call (the agent's `cwd`); required |
| `id` | `str` | Call ID, a new hex UUID per context; logged by `invoke_tool()` as `tool_ctx_id` |
| `caller_id` | `str \| None` | The `caller_id` passed to `invoke_tool()` |

`ToolCallResult` is a dataclass:

| Field | Type | Meaning |
|---|---|---|
| `text` | `str` | Text output |
| `structured_content` | `dict \| None` | Parsed JSON output, if any |
| `is_error` | `bool` | The call failed (non-zero exit, MCP error, blocked/rejected call) |

| Class | `type` | Execution |
|---|---|---|
| `PythonFunctionTool` | `function` | Calls a Python callable as `handler(**args)` (async handlers are run to completion with `run_sync`; the handler does not get the `ToolCallContext`). The return value is mapped by `to_tool_call_result()` (see below); an exception raised by the handler is logged and returned as `ToolCallResult(text=str(e), is_error=True)` |
| `ComputerTool` | `computer` | Runs a shell command via `subprocess.run(..., shell=True)`. Supports an optional `command_template` |
| `AppleScriptTool` | `computer` | `ComputerTool` with an `osascript -e '{command}'` template (macOS) |
| `ReadTool`, `WriteTool` | — | The built-in `read` and `write` tools (`geenii/tool/computer.py`), see [Built-in tools](#built-in-tools) |
| `PythonCliTool` | `python` | Like `ComputerTool`, intended for running Python scripts. Runs without a shell, in `ctx.cwd` |
| `SandboxTool` | `sandbox` | Runs a command inside a Docker container with security hardening (see [sandbox.md](sandbox.md)) |
| `McpTool` | `mcp_tool` | Forwards the call to an MCP server via fastmcp |
| `WebFetchTool` | — | The built-in `web_fetch` tool (`geenii/tool/webtools.py`), see [`web_fetch`](#web_fetch) |
| `ScriptTool` | `function` | Runs an executable script from a skill's `scripts/` directory, with the `args` string (`shlex`-split) as its arguments and the script's directory as cwd. Returns stdout and stderr joined by a newline as `text`, parsed into `structured_content` if that is valid JSON; a non-zero exit sets `is_error`. `register_skill_scripts()` (`geenii/skills.py`) registers one per script, named `{skill}__{script_stem}`, but nothing calls it at the moment, so skill scripts are not exposed as tools. See [skills.md](skills.md#scripts). |

`to_tool_call_result(result)` (`geenii/tool/common.py`) maps a handler's
return value: a `ToolCallResult` is passed through, `None` becomes empty text,
`str` is the text, `bytes` are decoded as UTF-8, a `dict` becomes JSON text
plus `structured_content`, a list or tuple becomes JSON text, an `Exception`
becomes `is_error=True` with the message as text, and anything else is
`str()`-ed.

`Tool` also provides definition mappers: `to_definition()` (internal/OpenAI
style), `to_openai()`, and `to_ollama()` — providers pick the one they need.

## Built-in tools

Two functions in `geenii/tools.py` register them:

- `init_builtin_os_tools()` registers `bash`, `python`, `read`, `write` and,
  through `init_core_os_tools()` (`geenii/core/tools.py`),
  `display_desktop_notification`.
- `init_builtin_webtools()` registers `web_fetch`.

`init_agent()` calls `init_builtin_os_tools()` when the agent spec's `tools`
list contains `read`, `write` or `bash`, and `init_builtin_webtools()` when it
contains `web_fetch`. All tools of a group are registered, but the model only
sees the ones in `allowed_tools`. `geenii tools`, the HTTP server and the
`/tools` info command always register both groups.

| Name | Type | Description |
|---|---|---|
| `bash` | ComputerTool | Run a single-line shell command on the local machine |
| `python` | ComputerTool | Run Python: the `command` argument is everything after the interpreter (e.g. `-m mymodule` or `script.py --flag`), and `python3 ` is put in front. It runs through the shell like `bash`, so it can execute an arbitrary command too |
| `read` | ReadTool | Read a text file |
| `write` | WriteTool | Write a text file |
| `display_desktop_notification` | PythonFunctionTool | Show a desktop notification (macOS, via `osascript`) |
| `web_fetch` | WebFetchTool | Fetch a URL over HTTP(S), see [`web_fetch`](#web_fetch) | In `read` and `write`, relative paths are resolved
against `ctx.cwd`, and only paths inside that directory, `GEENII_WORKING_DIR` or a
directory listed in the user settings' `allowed_dirs` (a list; any other value
is ignored) are accepted. The check runs on the fully resolved path, so `..`
segments and symlinks that lead outside are rejected, and the directory itself
(e.g. `.`) does not count as inside. A rejected path is an error result ("You
are not allowed to … this file: <path>") and logs a `SECURITY ALERT`. Other
failures (missing file, invalid or empty `file_path`) are error results too.
`write` overwrites existing files, writes an empty file when `contents` is
missing, and does not create parent directories. Both are tested in
`tests/geenii/test_file_tools.py`. The sandbox tools (`SandboxTool`) are not
registered by default.

### `web_fetch`

`WebFetchTool` sends a `GET` request with `httpx` and returns the response.

| Argument | Meaning |
|---|---|
| `url` | Required. Only `http` and `https` URLs are accepted |
| `parser` | `none` (raw body), `json`, `html` or `xml`. The schema advertises `html` as the default, but when the model leaves it out the tool uses `none` |

- **Limits:** at most 3 redirects, a 30-second timeout and 5 MB of content
  (`MAX_REDIRECTS`, `TIMEOUT`, `MAX_CONTENT_BYTES`); a larger response is an
  error result. The `User-Agent` is `geenii-web-fetch/1.0`.
- **Parsers:** `json` returns the parsed data pretty-printed; `html` returns the
  page title and its readable text (scripts, styles and `<head>` dropped, one
  line per block element); `xml` returns the indented document.
- **`structured_content`:** the final `url`, `status_code`, `content_type`,
  `redirects`, `fetched_at`, plus `data` (json), `title` and `body` (html) or
  `root_tag` (xml).
- **Errors:** an HTTP status of 400 or more is an error result with the start
  of the body; so are request failures, a body that doesn't parse, and invalid
  arguments.
- **Cache:** successful responses are cached by URL for an hour (`CACHE_TTL`)
  in `$GEENII_CACHE_DIR/web_fetch/`, unless caching is disabled
  (`--no-cache` / `GEENII_CACHE_DISABLED`).

### Command execution details

- The command runs in the `cwd` passed to `invoke()` (the agent's `cwd`, see
  [agents.md](agents.md#runtime-model)) via `ctx.cwd`.
- The command string is run through the shell (`shell=True`), so pipes,
  redirects and `&&` work. The `shlex`-split argument list is only logged.
- `${VAR}` / `$VAR` placeholders in the command are expanded from the tool
  invocation env. For agents that is the agent's variables and secrets
  ([`geenii agents env`](../cli-reference/agents.md#env)); the same env is also
  passed to the process.
- `text` is `stdout:\n<stdout>\nstderr:\n<stderr>`. On a non-zero exit code
  `EXITED WITH NON-ZERO EXIT CODE: <code>` is appended and `is_error` is set.
  On success, stdout that is a JSON **object** is also returned as
  `structured_content` (`PythonCliTool` only tries this for a zero exit code
  and non-empty stdout).
- **Tool filters** can restrict which commands a tool is allowed to execute.
  See the *Tool filtering* section below and [skills.md](skills.md) for how
  `allowed-tools` with argument-level patterns work.
- The HITL controller (see [agents.md](agents.md)) provides an additional
  approval gate. `geenii/sandbox.py` contains Docker sandbox helpers that are
  not yet wired into the tool pipeline — see [sandbox.md](sandbox.md) for the
  full design and integration roadmap.

## MCP tools

See [mcp.md](mcp.md) for the full MCP picture (config merging, client
lifetimes, CLI, HTTP API, web UI).

MCP servers are declared in `~/.geenii/mcp.json` and `$GEENII_WORKING_DIR/.geenii/mcp.json` (see
[configuration.md](../user-guide/configuration.md)). `init_agent()` calls
`init_mcp_server_tools(registry, server_names)` with the agent spec's
`mcp_servers`; servers not in that set are skipped, and an agent without
`mcp_servers` gets no MCP tools. For each selected server:

1. Each server is contacted through `McpClient` (a fastmcp wrapper) and its
   `tools/list` result is fetched, with one retry after a second (a server
   that still fails is skipped), and cached for 1 hour via `@cached` (empty
   results and failures are not cached). Discovery runs in the background
   loader, see [mcp.md](mcp.md#background-loading).
2. Each advertised tool is registered as an `McpTool` named
   `mcp__<server>__<tool>` (e.g. `mcp__duckduckgo__search`).

On invocation, `get_mcp_client_for_server()` returns the cached `McpClient`
for the owning server (one persistent connection per server, until
`close_mcp_clients()`), and `tools/call` is issued with the model-provided
arguments. The `CallToolResult` is mapped to a `ToolCallResult`:

- `text` — the first content item, if it is `TextContent`.
- `structured_content` — the result's `structured_content`, or else `text`
  parsed as JSON when that works.
- `is_error` — the MCP result's `is_error` flag, or `True` when the result is
  not a `CallToolResult`.

If connecting or calling the server raises, the exception is not re-raised:
the tool returns `ToolCallResult(text=str(e), structured_content={"error":
str(e)}, is_error=True)`.

`McpClient` targets the current MCP protocol via fastmcp's `mode="auto"`; a
server entry with `"legacy": true` in `mcp.json` uses `mode="legacy"`. Progress
notifications are printed to stdout; the server log and message handlers are
placeholders that do nothing yet. The client also exposes
`list_server_capabilities()`, and reads resources with
`get_resource_content()` / `download_resource()` (single-part text or blob
resources only).

## Invocation and logging

`invoke_tool(tool, args, env, cwd=None, caller_id="anonymous", secret_keys=None)`
(`geenii/tools.py`) builds a `ToolCallContext(cwd=cwd or GEENII_WORKING_DIR,
caller_id=caller_id)`, wraps
`tool.invoke(args=..., env=..., ctx=ctx)` and appends one JSON line per call to
`$GEENII_CACHE_DIR/logs/tool-use-YYYY-MM-DD.log`:

```json
{"timestamp": "...", "caller_id": "agent:default:call_1", "tool": "bash",
 "args": {...}, "env": {...}, "cwd": "...", "result": {"text": "...", "structured_content": null, "is_error": false}}
```

When the tool raises, `result` is `{"exception": ..., "traceback": ...}` and the
exception is re-raised. Env values are logged as `REDACTED`, here and in the
`Invoking tool …` line `invoke_tool` writes to the Python logger before the
call, when:

- the name is in `secret_keys` (an agent passes the names of its secrets,
  see [`geenii agents env`](../cli-reference/agents.md#env)), or
- the name contains `password`, `secret`, `api_key` or `token`, or one of its
  `_`-separated parts is `pass`, `passwd` or `pat` (case-insensitive; so
  `GITHUB_PAT` is redacted, `PATH` is not).

`_redact_env_vars()` returns a redacted copy, so the tool itself gets the real
values. Arguments and output are logged in full, so treat the log as
sensitive.

Callers and their `caller_id`:

| Caller | `caller_id` |
|---|---|
| `ToolCallTask` | `agent:<agent name>:<call_id>` |
| `geenii tools call` | `cli:tools` |
| `POST /tools/{name}/execute` | `web:tools` (runs in `GEENII_WORKING_DIR`) |

`ToolRegistry.invoke()` was removed; look the tool up with `registry.get(name)`
and call `invoke_tool()`.

## Registering your own tools

```python
from geenii.tool.registry import ToolRegistry

registry = ToolRegistry()


@registry.tool()
def greet(name: str) -> str:
    """Say hello."""
    return f"Hello, {name}!"


# or explicitly:
registry.register_function(my_fn, name="my_tool", description="...", parameters={...})
```

When `parameters` is omitted, a minimal JSON schema is derived from the
function signature (str/int/float/bool/list/dict annotations; parameters
without defaults become required).

A function tool does not see the `ToolCallContext`. A tool that needs the
call's working directory subclasses `Tool` and reads `ctx.cwd` in `invoke()`,
like `ReadTool`.

## How tools reach the model

1. The agent's `allowed_tools` set (from the agent spec's `tools` list or the
   CLI `--tools` flag) is sent with each `ChatCompletionRequest`.
2. The provider filters the registry's definitions down to the allowed names,
   converts them to its wire format, and attaches them to the model request.
3. Tool calls in the model response come back as `ToolCallContent` parts with a
   generated `call_id`; results are fed back as `ToolCallResultContent`
   messages, and the completion is re-generated (bounded by
   `LLMTask.MAX_TOOL_CALLS = 10` per response and `MAX_RECURSION = 10`).

A tool that is registered but not in `allowed_tools` is invisible to the model.

## Tool filtering

Tool filters add argument-level restrictions on top of the name-based
`allowed_tools` whitelist. They use a syntax inspired by Claude's
`allowed-tools` format:

```
ToolName                      # allow the tool with any arguments
ToolName(param:pattern)       # allow only when `param` matches `pattern`
```

Patterns use `fnmatch`-style wildcards (`*` matches anything). Tool name
matching is case-insensitive.

### Examples

```yaml
# In a skill's SKILL.md frontmatter:
allowed-tools: >-
  Bash(command:uname *), Bash(command:hostname *), Bash(command:date *),
  Bash(command:uptime *), read, write
```

This allows the `bash` tool only for commands starting with `uname`, `hostname`,
`date`, or `uptime`, while `read` and `write` are unrestricted. Any other
`bash` command (e.g. `rm -rf /`) is rejected before execution.

### Implementation (`geenii/tool/tool_filter.py`)

| Class | Purpose |
|---|---|
| `ToolFilter` | A single rule: tool name + optional parameter name and glob pattern |
| `ToolFilterSet` | A collection of rules. A tool call is allowed if **any** rule permits it. An empty set allows everything. |

Parsing handles comma-and-space-separated lists correctly even when patterns
contain spaces (e.g. `Bash(command:uname *)`), by tracking parenthesis depth.

### Enforcement layers

1. **LLM request** — `LLMTask._compute_effective_tools()` extracts the set of
   tool **names** from active skills' `ToolFilterSet` to decide which tools the
   model can see. This keeps tools with zero matching filters hidden from the
   model entirely.
2. **Invocation gate** — `ToolCallTask` checks active skills' tool filters
   against the tool name **and arguments** before executing. A blocked call
   returns an error result to the model without invoking the tool or prompting
   the HITL controller.
3. **HITL** — calls that pass the filter still go through the human-in-the-loop
   approval flow.

### Programmatic use

```python
from geenii.tool.tool_filter import ToolFilter, ToolFilterSet

# Parse a single filter
f = ToolFilter.parse("Bash(command:uname *)")
f.allows("bash", {"command": "uname -a"})  # True
f.allows("bash", {"command": "rm -rf /"})  # False

# Parse a set
fs = ToolFilterSet.parse("Bash(command:uname *), Bash(command:date *), read")
fs.allows("bash", {"command": "date +%Y"})  # True
fs.allows("read", {})  # True
fs.allows("bash", {"command": "curl evil"})  # False
fs.tool_names()  # {"bash", "read"}
```

## CLI

```bash
geenii tools list                 # all registered tools (built-in + MCP)
geenii tools inspect <name>       # schema and description
geenii tools call <name> -a key=value -a key2=value2
```

## HTTP API

The [server](server.md) keeps one `ToolRegistry` with the built-in tools and
the tools of every server in `mcp.json`, and exposes it to the web UI's tools
view. The MCP-specific `/api/v1/mcp/…` routes are described in
[mcp.md](mcp.md#http-api).

| Method & path | Body | Response |
|---|---|---|
| `GET /api/v1/tools/` | — | Array of `{name, type, description, parameters}` |
| `POST /api/v1/tools/{name}/execute` | Arguments as a JSON object | `ToolCallResult` as `{text, structured_content, is_error}`; 404 Problem for unknown tools, 500 Problem when the tool raises |

Execution skips tool filters and HITL approval, so it runs any command
`bash`/`python` are given.
