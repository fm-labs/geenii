# geenii tools

List, inspect, and call registered tools.

## Synopsis

```
geenii tools <command>
```

## Commands

### list

```
geenii tools list
```

List all registered tools (built-in and MCP), showing name, description, and
type.

### inspect

```
geenii tools inspect <TOOL_NAME>
```

Show the full schema and description of a tool, including name, type,
parameters, and description.

### call

```
geenii tools call <TOOL_NAME> [OPTIONS]
```

Invoke a tool directly with the provided arguments. Prints the result's error
flag, text and structured content. The call is logged to
`$GEENII_CACHE_DIR/logs/tool-use-YYYY-MM-DD.log` with caller `cli:tools`.

#### Options

| Option | Short | Description |
|---|---|---|
| `--args` | `-a` | Tool argument in `key=value` format (repeatable) |

#### Examples

```bash
geenii tools list
geenii tools inspect bash
geenii tools call bash -a command="echo hello"
```
