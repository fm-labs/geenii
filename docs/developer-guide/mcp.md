# MCP Servers

Geenii is an [MCP](https://modelcontextprotocol.io) **client**. It connects to
the MCP servers declared in `mcp.json` and uses them in four places:

| Where | What it does with MCP |
|---|---|
| Agents | Tools from the servers in an agent's `mcp_servers` become callable tools (`mcp__<server>__<tool>`) |
| CLI | `geenii mcp server …` lists servers and inspects, calls and downloads from them |
| HTTP server | `/api/v1/mcp/…` lists, adds, edits and deletes servers, fetches a server's tools and calls them. MCP tools also show up in `/api/v1/tools/` |
| Web UI | Console → Configure → MCP shows the servers, their config and their tools, has a form to run each tool, and an editor to add, edit and delete servers |

Geenii does not host an MCP server itself, and does not use MCP prompts yet.

## Code map

| Module | Role |
|---|---|
| `geenii/mcp_config.py` | Reads and merges `mcp.json`, writes server entries to the root `mcp.json`, expands `${VAR}` placeholders, caches the merged config, and caches one `McpClient` per server |
| `geenii/mcp_client.py` | `McpClient`: a synchronous wrapper around fastmcp's async `Client` |
| `geenii/tool/mcp_tool.py` | `McpTool`: a `Tool` that forwards `invoke()` to an MCP server |
| `geenii/tool/registry.py` | `ToolRegistry.register_mcp_tools()` turns a `tools/list` result into `McpTool`s |
| `geenii/tools.py` | `read_mcp_server_tools()` (discovery, cached) and `init_mcp_server_tools()` |
| `geenii/cli/mcp_cli.py` | The `geenii mcp` command group |
| `geenii/server/mcp_routes.py` | The `/mcp` HTTP routes |
| `geenii-ui/src/app/mcp-servers/` | React providers and components for the MCP view |
| `geenii-ui/src/app/catalog/` | Docker MCP Catalog browser (static catalog data, see [web-ui.md](web-ui.md#docker-mcp-catalog)) |

## Configuration

Servers are declared in a standard `mcpServers` map. Two files are read, and
later entries win when a server name is in both:

1. `~/.geenii/mcp.json` (user-wide, the **root** file, `get_root_mcp_config_path()`)
2. `$GEENII_WORKING_DIR/.geenii/mcp.json` (project)

`get_mcp_config_paths()` returns both, in merge order. A missing file logs a
warning, and a file with invalid JSON logs an error. In both cases it's
skipped. Besides `mcpServers`, each file may have a top-level `env` map of
values for `${VAR}` placeholders (see [Variable expansion](#variable-expansion)),
merged the same way. The format is in
[configuration.md](../user-guide/configuration.md#mcpjson--mcp-servers).

Each entry is passed unchanged to fastmcp's `MCPConfig`, except for one
geenii-only key: `"legacy": true`. It is removed before the entry reaches
fastmcp, and it switches the client to `mode="legacy"` for servers that only
support an older protocol version. The default is `mode="auto"`.

| Key | Meaning |
|---|---|
| `type` | `stdio` or `http`. Optional: the HTTP API guesses it from `command` / `url` when it's missing |
| `command`, `args`, `env` | stdio transport: the process to start and its environment |
| `url`, `headers` | HTTP transport |
| `legacy` | Use the legacy protocol mode (geenii-only) |

`get_mcp_config()` reads the files once per process. `get_mcp_config(reload=True)`
reads them again. Reloading on its own does **not** replace clients that are
already cached (see [Clients and connections](#clients-and-connections)).
Writes through the API do, for the server they change.

### Variable expansion

String values may contain `${VAR}` placeholders:

```json
{
  "env": {"GITHUB_TOKEN": "ghp_…"},
  "mcpServers": {
    "github": {
      "url": "https://api.githubcopilot.com/mcp/",
      "headers": {"Authorization": "Bearer ${GITHUB_TOKEN}"}
    }
  }
}
```

`get_mcp_config_for_server(name, compile=True)` returns a **copy** of the entry
with the placeholders replaced by values from the merged top-level `env` map
(`_expand_env_vars_in_server_config()`). The cached config and the files keep
the placeholders. `get_mcp_client_for_server()` uses the compiled entry, so
clients connect with real values.

- Expanded in: `command`, `url`, each item of `args`, and the values of `env`
  and `headers`. Other keys and non-string values are left as they are.
- Names match `\w+` (letters, digits, `_`). A name without a value stays as the
  literal `${NAME}`; it isn't an error.
- Values come only from the `env` map in `mcp.json`, not from the process
  environment.

### Writing the config

The API writes only the **root** file. The project file is never changed.

| Function | Effect |
|---|---|
| `read_root_mcp_config()` | The root file as-is. A missing file reads as `{"mcpServers": {}}` |
| `write_root_mcp_config(data)` | Writes the root file atomically (temp file + `os.replace`), creating `~/.geenii/` if needed, then reloads the merged config |
| `save_mcp_server_config(name, cfg)` | Adds or replaces one entry, keeping the other top-level keys such as `env` |
| `delete_mcp_server_config(name)` | Removes one entry. Returns `False` if the root file doesn't have it |

Saving or deleting closes and drops the server's cached client, so its next
use connects with the new config. Entries are written as sent, with any
`${VAR}` placeholders kept.

| Environment variable | Default | Effect |
|---|---|---|
| `GEENII_MCP_INIT_TIMEOUT` | `30` | Seconds fastmcp waits for a server's `initialize` handshake |

## Clients and connections

`McpClient(server_name, server_config)` wraps fastmcp's `Client`, which is
async-only. Every public method runs its coroutine on the shared async bridge
loop (`run_sync`, `utils/async_bridge.py`). This keeps each connection on one
event loop, whichever thread calls it.

- **Connection:** the client connects lazily, on the first call, and the
  connection stays open until `close()`. For a stdio server, the server process
  runs for as long as the connection is open.
- **List cache:** the results of `list_tools()`, `list_resources()` and
  `list_prompts()`, and resource reads, are cached for the client's lifetime.
  `info()` (capabilities, tools and resources) is cached too.
- **Methods:** `info()`, `list_server_capabilities()`, `list_tools()`,
  `list_resources()`, `list_prompts()`, `call_tool(name, args)`,
  `get_resource_content(uri)` and `download_resource(uri, path, overwrite)`.
  Only single-part text or blob resources are supported.
- **Handlers:** progress notifications are printed to stdout. The log and
  message handlers do nothing yet.

There are two ways to get a client:

| How | Lifetime | Used by |
|---|---|---|
| `get_mcp_client_for_server(name)` | One cached client per server name for the whole process. `close_mcp_clients()` closes them all (it runs at exit) | `McpTool.invoke()`, the HTTP routes, the CLI |
| `McpClient(name, conf)` directly | Short-lived, closed right after use | `read_mcp_server_tools()` (discovery) |

So the first listing of a server's tools at startup starts the server once, and
the first tool call starts it a second time, on its own long-lived connection.

## MCP tools

`init_mcp_server_tools(registry, server_names=None)` does the following for
each configured server (or only for those in `server_names`):

1. `read_mcp_server_tools()` fetches `tools/list` through a short-lived client.
   The result is cached for one hour with `@cached(ttl=3600, cache_if=bool)`,
   keyed by server name and config. Empty results are not cached, so an
   unreachable server is tried again next time. There's no retry: a failed
   listing logs an error and skips the server.
2. `registry.register_mcp_tools()` registers one `McpTool` per tool, named
   `mcp__<server>__<tool>`. It uses the tool's `description` and `input_schema`.

Callers:

- **Agents:** `init_agent()` passes the agent spec's `mcp_servers`, so an agent
  only gets tools from the servers it lists, and none without `mcp_servers`.
- **HTTP server:** at startup, the app's `tool_registry` loads tools from
  **all** configured servers. It does this in a worker thread, because
  discovery blocks. Startup takes as long as the slowest server takes to
  respond, up to the init timeout.
- **CLI:** `geenii tools` and `geenii ai`.

`McpTool.invoke()` calls the tool through the cached client and maps the
`CallToolResult` to a `ToolCallResult`:

| `ToolCallResult` field | Source |
|---|---|
| `text` | The first content item, if it's `TextContent` |
| `structured_content` | The result's `structured_content`, or else `text` parsed as JSON |
| `is_error` | The result's `is_error` flag. `True` for any other result type |

Exceptions are not re-raised. They become
`ToolCallResult(text=str(e), structured_content={"error": str(e)}, is_error=True)`.
For tool-use logging, HITL and filtering, MCP tools go through the same
machinery as every other tool (see [tools.md](tools.md)).

## CLI

```bash
geenii mcp server list                          # name, transport, command/url
geenii mcp server inspect <server>              # the raw config entry as JSON
geenii mcp server info <server>                 # capabilities, tools, resources
geenii mcp server tools <server>                # tools/list result
geenii mcp server tool_info <server> <tool>     # one tool definition
geenii mcp server tool_exec <server> <tool> -a key=value
geenii mcp server tool_exec <server> <tool> -j '{"key": "value"}'
geenii mcp server resource <server> <uri> [--download] [--overwrite]
```

`resource --download` saves to `$GEENII_CACHE_DIR/mcp/<server>/r/<path>`, where
`<path>` is the part of the URI after `://`, or else an MD5 hash of the URI.
Every option is in the [CLI reference](../cli-reference/mcp.md).

## HTTP API

The routes are in `server/mcp_routes.py`, mounted under `/api/v1` with the same
`dep_current_user` dependency as the other route modules. The endpoints are
sync functions, so FastAPI runs them in its threadpool, where blocking MCP
calls don't stall the event loop.

| Method & path | Body | Response |
|---|---|---|
| `GET /mcp/servers?reload=false` | — | Array of server summaries, in config order. `reload=true` reads `mcp.json` again first |
| `POST /mcp/servers` | `{"name": str, "config": {…}}` (`McpServerCreateRequest`) | `201` with the new server's summary. Adds the entry to the root `mcp.json` |
| `GET /mcp/servers/{name}` | — | Summary merged with `McpClient.info()`: `server_capabilities`, `tools`, `resources`. Connects to the server (starts it, for stdio) |
| `GET /mcp/servers/{name}/config` | — | The full `mcp.json` entry (merged config), with `env` and `headers` values masked. Doesn't connect |
| `PUT /mcp/servers/{name}` | The full entry (`{…}`) | The updated summary. Replaces the entry in the root `mcp.json` |
| `DELETE /mcp/servers/{name}` | — | `204`. Removes the entry from the root `mcp.json` |
| `POST /mcp/servers/{name}/tool/call` | `{"tool_name": str, "arguments": {}}` (`MCPToolCallRequest`) | The raw MCP `CallToolResult` as JSON (`content`, `structured_content`, `is_error`, …) |

Errors use the standard Problem body (see [server.md](server.md#errors)):

| Status | When |
|---|---|
| `400` | Create: the name isn't `[A-Za-z0-9_-]+`. Create/update: the entry has neither `command` nor `url`, `args` isn't a list of strings, `env` / `headers` isn't an object of strings, or a value is `********` with no stored value to keep |
| `404` | The server name isn't in the config |
| `409` | Create: the name is already in the merged config. Update/delete: the server exists, but only in the project `mcp.json`, which the API doesn't write |
| `502` | Connecting to the server or calling the tool raises |

**Masked values:** `GET …/config` returns every `env` and `headers` value as
`********`. In a `PUT` body, a value of `********` means "keep the stored
value" for that key, so a client can send an entry back without knowing its
secrets. Keys left out of the body are removed. The same placeholder in a
`POST` body is rejected, since there's nothing stored yet.

A **server summary** has this shape:

```json
{
  "name": "duckduckgo",
  "type": "stdio",
  "url": null,
  "command": "docker",
  "args": ["run", "--rm", "-i", "mcp/duckduckgo"],
  "env": {"API_KEY": "********"}
}
```

`env` **values** are masked, because they often hold secrets. `headers` and any
other keys are left out. The full entry, with `env` and `headers` masked, is at
`GET /mcp/servers/{name}/config`; the CLI `inspect` command shows it unmasked.

All JSON from the MCP SDK is snake_case (`input_schema`, `output_schema`,
`structured_content`, `is_error`), because it's produced by `model_dump()`
without aliases. Frontend code has to use the same names (see `McpServerTool`
in `geenii-ui/src/app/mcp-servers/types.ts`).

These endpoints call the server directly, through the cached client. This
differs from `POST /tools/mcp__<server>__<tool>/execute`, which goes through
`McpTool` and `invoke_tool()`: that one maps the result to a `ToolCallResult`
and writes a tool-use log entry. The `/mcp` tool call writes no tool-use log.

## Web UI

Route: `#/console/configure/mcp-servers` (`console/configure-page.tsx` →
`McpServersSettingsView`).

```
McpServersSettingsView
└── McpServersProvider              GET /mcp/servers           servers, loading, error, refresh(reload),
    │                                                          getServerConfig, createServer,
    │                                                          updateServer, deleteServer
    └── McpServersAdminView         filter, server list, selection, add / edit / delete
        ├── McpServerConfigEditor   in a Sheet                 form ↔ JSON editor for one mcp.json entry
        └── McpServerProvider       keyed by server name       tools, resources, loading, loaded, error,
            │                                                  fetchTools(), callTool(name, args)
            ├── McpServerViewHead   name, type, command/url, edit, delete, close
            ├── McpServer           config fields ↔ raw JSON toggle
            └── McpServerActions    GET /mcp/servers/{name} on mount; tool list
                └── McpServerToolForm   rjsf form from input_schema → POST …/tool/call
```

- **Server list:** the filter matches name and command/url. Refresh calls
  `refresh(true)`, which reads `mcp.json` again on the server.
- **Add / edit / delete:** "Add server" opens `McpServerConfigEditor` empty;
  Edit first loads the full entry with `GET …/config`, because the list summary
  leaves out `headers`, `cwd`, `timeout` and other keys. Saving calls
  `POST /mcp/servers` or `PUT /mcp/servers/{name}`; Delete asks for
  confirmation, then calls `DELETE`. Each refreshes the list afterwards. Masked
  values the user leaves empty are sent back as `********` and so kept. The
  name can't be changed when editing.
- **Editor:** stdio (command, args, env, cwd) or remote (URL, Streamable HTTP
  or SSE, headers), plus description, timeout and `legacy`. Keys the form has
  no field for are passed through unchanged. JSON mode edits the same entry as
  text. Validation mirrors the server's (name pattern, command or URL
  required, unique names).
- **Details card:** keyed by server name, so a server's tools are fetched once
  each time it's selected. The tools Refresh button fetches again, but gets
  the same result back (see [Known issues](#known-issues)).
- **Tool results:** shown as success or error from `is_error`, with the time
  taken. Text content is shown as text, then `structured_content` as JSON, then
  the raw result, collapsed.
- **Shared code:** the parameter table is `ParametersTable` from
  `app/tools/tools.view.tsx`, shared with the Tools view.

## Tests

```bash
uv run pytest tests/geenii/test_mcp_config.py tests/geenii/test_mcp_routes.py
```

| File | Covers |
|---|---|
| `tests/geenii/test_mcp_config.py` | `${VAR}` expansion (which fields, unknown names, non-string values), merging the root and project files, compiled configs being copies, and the root-file write helpers (create, keep other keys, reload, drop cached clients, delete) |
| `tests/geenii/test_mcp_routes.py` | The `/mcp/servers` CRUD routes: masking, create validation and name clashes, keeping masked values on update, `404` / `409` for unknown and project-only servers, delete |

Both use the `mcp_dirs` fixture in `tests/geenii/conftest.py`. It points the
root and project `mcp.json` at temp dirs and empties the config and client
caches, so the real `~/.geenii/mcp.json` is never read or written. The route
tests use `TestClient(app)` without `with`, so the app's lifespan, which
connects to every configured server to discover its tools, doesn't run. No
test connects to an MCP server.

## Known issues

- **Stale clients after a manual config change:** `get_mcp_client_for_server()`
  caches clients by name only. Changes made through the API drop the cached
  client, but after you edit `mcp.json` by hand, `reload=true` updates the
  server list while tool calls and `GET /mcp/servers/{name}` keep using the
  old connection and config until the process restarts.
- **Project file overrides API edits:** a server defined in both files is
  read from the project `mcp.json`. Its update succeeds against the root file,
  but has no effect until the project entry is removed.
- **Registered tools aren't updated:** adding, changing or deleting a server
  doesn't touch the tools already registered in the server's `tool_registry`
  or in running agents. New servers' tools show up after a restart.
- **Tool lists never refresh:** `McpClient` never invalidates its list cache,
  so a server's new or changed tools don't show up until the process restarts.
  Discovery has its own one-hour cache on top of that.
- **Slow first request:** the first `GET /mcp/servers/{name}` for a stdio
  server starts the server process, for example `docker run`, and can take up
  to `GEENII_MCP_INIT_TIMEOUT` seconds. It holds a threadpool worker while it
  waits.
- **Noisy logs:** `get_mcp_client_for_server()` logs a warning every time it
  reuses a cached client.
- **CLI closes cached clients:** the CLI commands `close()` the cached client
  when they finish. That's fine for one-shot CLI runs, but don't copy the
  pattern into long-lived code that shares the cache.
- **Only the first content item:** `McpTool` maps only the first content item.
  Images, multiple text parts and embedded resources are dropped. The `/mcp`
  HTTP route returns them all.
