# geenii mcp

Manage MCP servers and tools.

## Synopsis

```
geenii mcp server <command>
```

All MCP commands live under the `server` subgroup.

## Commands

### server list

```
geenii mcp server list
```

List all MCP servers defined in the configuration.

### server inspect

```
geenii mcp server inspect <SERVER_ID>
```

Show the full server configuration as JSON.

### server info

```
geenii mcp server info <SERVER_ID>
```

Connect to the server and print its capabilities, tools and resources as JSON.

### server tools

```
geenii mcp server tools <SERVER_ID>
```

List all tools provided by a server as JSON (name, description, input schema
and the other tool fields).

### server tool_info

```
geenii mcp server tool_info <SERVER_ID> <TOOL_NAME>
```

Show the definition of one tool as JSON.

### server tool_exec

```
geenii mcp server tool_exec <SERVER_ID> <TOOL_NAME> [OPTIONS]
```

Execute a tool on a server and print the text of the first content item of
the result.

#### Options

| Option | Short | Description |
|---|---|---|
| `--arg` | `-a` | Tool argument in `key=value` format (repeatable) |
| `--json-args` | `-j` | Tool arguments as a JSON string |

#### Examples

```bash
geenii mcp server tool_exec my-server my-tool -a key=value
geenii mcp server tool_exec my-server my-tool -j '{"key": "value"}'
```

### server resource

```
geenii mcp server resource <SERVER_ID> <RESOURCE_URI> [OPTIONS]
```

Read a resource from the server and print it as UTF-8 text. Only single-part
text or blob resources are supported.

#### Options

| Option | Description |
|---|---|
| `--download` | Save the resource to `$GEENII_CACHE_DIR/mcp/<SERVER_ID>/r/<path>` instead of printing it. `<path>` is the part after `://`, or an MD5 hash of the name if it has no scheme |
| `--overwrite` | Replace an existing downloaded file |

#### Examples

```bash
geenii mcp server resource my-server file://docs/readme.md
geenii mcp server resource my-server ui://widget/index.html --download
```
