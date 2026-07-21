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

Invoke a tool directly with the provided arguments.

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
