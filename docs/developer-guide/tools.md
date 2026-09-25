# Tools

A tool is a named, schema-described callable that the model can invoke during a
chat completion. Tools are held in a `ToolRegistry` (`geenii/tool/registry.py`);
each agent owns its own registry, populated at first prompt with the built-in
tools and all configured MCP server tools.

## Tool types

All tools subclass `Tool` (`geenii/tool/common.py`), which carries `name`,
`description`, and a JSON-Schema `parameters` dict, and implements
`async invoke(args, env, **kwargs)`.

| Class | `type` | Execution |
|---|---|---|
| `PythonFunctionTool` | `function` | Calls a Python callable (sync handlers run in the executor, async handlers awaited) |
| `ComputerTool` | `computer` | Runs a shell command via `subprocess` (no shell interpretation; the command string is `shlex`-split). Supports an optional `command_template` |
| `AppleScriptTool` | `computer` | `ComputerTool` with an `osascript -e '{command}'` template (macOS) |
| `PythonCliTool` | `python` | Like `ComputerTool`, intended for running Python scripts |
| `SandboxTool` | `sandbox` | Runs a command inside a Docker container with security hardening (see [sandbox.md](sandbox.md)) |
| `McpTool` | `mcp_tool` | Forwards the call to an MCP server via fastmcp |
| `ScriptTool` | `function` | Runs an executable script from a skill's `scripts/` directory. JSON is passed on stdin; stdout is returned. Auto-registered when a skill is activated, named `{skill}__{script_stem}`. See [skills.md](skills.md). |

`Tool` also provides definition mappers: `to_definition()` (internal/OpenAI
style), `to_openai()`, and `to_ollama()` — providers pick the one they need.

## Built-in tools

Registered by `init_builtin_tools()` (`geenii/tools.py`) on every agent:

| Name | Type | Description |
|---|---|---|
| `bash` | ComputerTool | Run a single-line shell command on the local machine |
| `python` | ComputerTool | Run a python command line (e.g. `python3 script.py`) — note: this executes an arbitrary command, same mechanics as `bash` |
| `sandbox_python` | SandboxTool | Run a Python command in a Docker sandbox (requires a selected skill) |
| `sandbox_bash` | SandboxTool | Run a shell command in a Docker sandbox (requires a selected skill) |
| `display_desktop_notification` | PythonFunctionTool | Show a desktop notification (from `geenii/core/tools.py`) |

`geenii/core/tools.py` additionally defines a module-level `geenii_tools`
registry with decorator-registered utilities (`file_exists`, `file_read`,
`file_write`, `bash`); apart from `display_desktop_notification`
these are not wired into agents yet.

### Command execution details

- The command string is split with `shlex` and executed **without** a shell —
  pipes, redirects, and `&&` do not work.
- `${VAR}` / `$VAR` placeholders in the command are expanded from the tool
  invocation env (notably `SKILL_NAME` — the comma-separated list of active
  skill names — see [skills.md](skills.md)).
- stdout is returned to the model; on a non-zero exit code, stderr and the exit
  code are appended.
- **Tool filters** can restrict which commands a tool is allowed to execute.
  See the *Tool filtering* section below and [skills.md](skills.md) for how
  `allowed-tools` with argument-level patterns work.
- The HITL controller (see [agents.md](agents.md)) provides an additional
  approval gate. `geenii/sandbox.py` contains Docker sandbox helpers that are
  not yet wired into the tool pipeline — see [sandbox.md](sandbox.md) for the
  full design and integration roadmap.

## MCP tools

MCP servers are declared in `$GEENII_DIR/mcp.json` (see
[configuration.md](../user-guide/configuration.md)). During agent initialization
(`init_mcp_server_tools`):

1. Each server is contacted through `McpClient` (a fastmcp wrapper) and its
   `tools/list` result is fetched — with one retry, and cached for 1 hour via
   `@cached`, so a dead server doesn't stall every run.
2. Each advertised tool is registered as an `McpTool` named
   `mcp__<server>__<tool>` (e.g. `mcp__duckduckgo__search`).

On invocation, a client for the owning server is created and
`tools/call` is issued with the model-provided arguments. Connections are
currently established per call, not pooled.

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

## How tools reach the model

1. The agent's `allowed_tools` set (from the agent spec's `tools` list or the
   CLI `--tools` flag) is sent with each `ChatCompletionRequest`.
2. The provider filters the registry's definitions down to the allowed names,
   converts them to its wire format, and attaches them to the model request.
3. Tool calls in the model response come back as `ToolCallContent` parts with a
   generated `call_id`; results are fed back as `ToolCallResultContent`
   messages, and the completion is re-generated (bounded by
   `LLMTask.MAX_TOOL_CALLS = 5`).

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
f.allows("bash", {"command": "uname -a"})   # True
f.allows("bash", {"command": "rm -rf /"})    # False

# Parse a set
fs = ToolFilterSet.parse("Bash(command:uname *), Bash(command:date *), read")
fs.allows("bash", {"command": "date +%Y"})   # True
fs.allows("read", {})                        # True
fs.allows("bash", {"command": "curl evil"})  # False
fs.tool_names()                              # {"bash", "read"}
```

## CLI

```bash
geenii tools list                 # all registered tools (built-in + MCP)
geenii tools inspect <name>       # schema and description
geenii tools call <name> -a key=value -a key2=value2
```
