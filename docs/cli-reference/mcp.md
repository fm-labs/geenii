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

### server show

```
geenii mcp server show <SERVER_ID>
```

Show the full server configuration as JSON.

### server tools

```
geenii mcp server tools <SERVER_ID>
```

List all tools provided by a server.

### server tool_exec

```
geenii mcp server tool_exec <SERVER_ID> <TOOL_NAME> [OPTIONS]
```

Execute a tool on a server.

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
