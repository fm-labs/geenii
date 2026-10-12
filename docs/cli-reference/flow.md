# geenii flow

Run and inspect flows: step pipelines defined in a `.toml` or `.json` file.
Flows run locally in the CLI process; they don't need the daemon. For the
file format, the step types and how steps pass data, see the developer guide
page [Flow](../developer-guide/flow.md).

## Synopsis

```
geenii flow <command> [OPTIONS]
```

## Commands

### run

```
geenii flow run <PATH> [OPTIONS]
```

Run the flow in `PATH`. Step events (start, end and any events the steps
yield, e.g. log lines) are printed to **stderr** as they happen. When the flow
is done, a summary is printed to **stdout**: the status of each step, then the
flow output (the output of the last successful step) as JSON.

#### Options

| Option | Short | Description |
|---|---|---|
| `--input` | `-i` | Flow input, available as `${input}` and passed to the root steps. Parsed as JSON if possible, otherwise used as a plain string. `-` reads it from stdin |
| `--var KEY=VALUE` | `-v` | Set a flow variable (`${vars.KEY}`), overriding the file's `[vars]`. VALUE is parsed as JSON if possible. Repeatable |
| `--max-workers` | `-w` | Number of steps that may run at the same time, overriding `max_workers` in the file |
| `--json` | | Print the full `FlowResult` as JSON instead of the summary |
| `--quiet` | `-q` | Don't print step events |
| `--step-module MODULE` | `-m` | Import a Python module that registers custom steps with `@register_step`. Repeatable |

#### Exit codes

| Code | Meaning |
|---|---|
| `0` | The flow succeeded |
| `1` | The flow failed or was aborted, the file is invalid, or the graph is invalid (unknown step in an edge, cycle) |
| `2` | Invalid command-line usage (e.g. `--var` without `=`) |

#### Examples

```bash
geenii flow run examples/flow_example.toml
```

```bash
geenii flow run my_flow.toml -i '{"url": "https://example.com"}' -v env=prod -w 4
```

```bash
echo "some text" | geenii flow run my_flow.toml -i - -q --json
```

### validate

```
geenii flow validate <PATH> [--step-module MODULE ...]
```

Check a flow without running it, and print its execution order with each
step's predecessors. It checks:

- that the file can be read and has a valid structure (step fields, unique
  step ids),
- the graph: edges to unknown steps and cycles,
- that every step type exists (registered, or importable as
  `package.module:ClassName`).

It doesn't validate step configs, because `${...}` references in a config can
only be resolved during a run. All problems are printed to stderr, and the
command exits with code 1 if there are any.

```
$ geenii flow validate examples/flow_example.toml
Flow 'example' is valid (4 steps, max_workers=1)

Execution order:
  step0 [echo]
  step1 [read_http]  (after step0)
  step2 [execute_command]  (after step1)
  step3 [execute_script]  (after step2)
```

### steps

```
geenii flow steps [--step-module MODULE ...]
```

List the registered step types with the first line of their docstring. Use
`-m` to include custom steps from your own modules.

```
$ geenii flow steps
echo                 Returns the configured message, or the step input if no message is set
execute_command      Runs a command in a subprocess
execute_script       Runs a Python script in a separate interpreter process.
read_http            Sends an HTTP request. `body` is sent as JSON; a JSON response is parsed into `data`.
```
