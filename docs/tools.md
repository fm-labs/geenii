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
| `McpTool` | `mcp_tool` | Forwards the call to an MCP server via fastmcp |

`Tool` also provides definition mappers: `to_definition()` (internal/OpenAI
style), `to_openai()`, and `to_ollama()` — providers pick the one they need.

## Built-in tools

Registered by `init_builtin_tools()` (`geenii/tools.py`) on every agent:

| Name | Type | Description |
|---|---|---|
| `execute_command` | ComputerTool | Run a single-line shell command on the local machine |
| `execute_python` | ComputerTool | Run a python command line (e.g. `python3 script.py`) — note: this executes an arbitrary command, same mechanics as `execute_command` |
| `display_desktop_notification` | PythonFunctionTool | Show a desktop notification (from `geenii/core/tools.py`) |

`geenii/core/tools.py` additionally defines a module-level `geenii_tools`
registry with decorator-registered utilities (`file_exists`, `file_read`,
`file_write`, `execute_command`); apart from `display_desktop_notification`
these are not wired into agents yet.

### Command execution details

- The command string is split with `shlex` and executed **without** a shell —
  pipes, redirects, and `&&` do not work.
- `${VAR}` / `$VAR` placeholders in the command are expanded from the tool
  invocation env (notably `SKILL_NAME`, `SKILL_DIR`, `SCRIPT_DIR` when a skill
  is selected — see [skills.md](skills.md)).
- stdout is returned to the model; on a non-zero exit code, stderr and the exit
  code are appended.
- There is no allowlist/sandboxing policy yet; the HITL controller (see
  [agents.md](agents.md)) is the only gate. `geenii/sandbox.py` contains Docker
  sandbox helpers that are not yet wired in.

## MCP tools

MCP servers are declared in `$GEENII_DIR/mcp.json` (see
[configuration.md](configuration.md)). During agent initialization
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

## CLI

```bash
geenii tools list                 # all registered tools (built-in + MCP)
geenii tools inspect <name>       # schema and description
geenii tools call <name> -a key=value -a key2=value2
```
