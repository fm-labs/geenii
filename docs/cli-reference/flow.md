# geenii flow

Run and inspect flows: step pipelines defined in a `.yaml`/`.yml`, `.json` or `.toml` file.
Flows run locally in the CLI process; they don't need the daemon. For the
file format, the processors and how steps pass data, see the developer guide
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
| `--snapshot FILE` | `-s` | Write a JSON snapshot (flow definition, input, status and step results) to FILE when the run starts, after steps finish and when the run ends. See [Snapshots](../developer-guide/flow.md#snapshots) |
| `--context-id ID` | | Id of the run, shown in the summary and stored in the result and snapshot. Default: a generated UUID |
| `--processor-module MODULE` | `-m` | Import a Python module that registers custom processors with `@register_processor`. Repeatable |

#### Exit codes

| Code | Meaning |
|---|---|
| `0` | The flow succeeded |
| `1` | The flow failed or was aborted, the file is invalid, or the graph is invalid (unknown step in an edge, cycle) |
| `2` | Invalid command-line usage (e.g. `--var` without `=`) |

#### Examples

```bash
geenii flow run examples/flow_example.yaml
```

```bash
geenii flow run my_flow.yaml -i '{"url": "https://example.com"}' -v env=prod -w 4
```

```bash
echo "some text" | geenii flow run my_flow.yaml -i - -q --json
```

```bash
geenii flow run my_flow.yaml --snapshot run.json
```

### validate

```
geenii flow validate <PATH> [--strict] [--processor-module MODULE ...]
```

Check a flow without running it, and print its execution order with each
step's predecessors. It checks:

- that the file can be read and has a valid structure (step fields, unique
  step ids),
- the graph: edges to unknown steps and cycles,
- that every step's processor exists (registered, or importable as
  `package.module:ClassName`).

It doesn't validate step config values, because `${...}` references in a
config can only be resolved during a run. All problems are printed to stderr,
and the command exits with code 1 if there are any.

It also warns about `${...}` references to a step that the referencing step
doesn't depend on (directly or indirectly through `depends_on` or edges), to the
step itself, or to an unknown name. Such a reference may fail when steps run in
parallel. Warnings are printed to stderr as `warning: ...` and don't change the
exit code, unless `--strict` is given: then any warning exits with code 1.
`geenii flow run` logs the same warnings and runs the flow anyway.

```
$ geenii flow validate examples/flow_example.yaml
Flow 'example' is valid (4 steps, max_workers=1)

Execution order:
  step0 [echo]
  step1 [read_http]  (after step0)
  step2 [execute_command]  (after step1)
  step3 [execute_script]  (after step2)
```

### graph

```
geenii flow graph <PATH> [OPTIONS]
```

Print the flow's graph (steps as nodes, labelled with id and processor; edges as
arrows) as **Mermaid** or **Graphviz DOT**, or render it to an image.

#### Options

| Option | Short | Description |
|---|---|---|
| `--format` | `-f` | `mermaid`, `dot`, `svg`, `png` or `pdf`. Default: taken from the `--output` file extension, otherwise `mermaid` |
| `--output FILE` | `-o` | Write to FILE instead of stdout. Required for image formats |
| `--direction` | `-d` | Layout direction: `LR` (left to right, default), `TB`, `RL`, `BT` |
| `--processor-module MODULE` | `-m` | As for `run` |

File extensions used when `--format` isn't given: `.mmd`, `.mermaid` and `.md`
become `mermaid`; `.dot` and `.gv` become `dot`; `.svg`, `.png` and `.pdf` are
rendered as images. Any other extension gets `mermaid`.

Image formats are rendered with Graphviz, so the `dot` command must be
installed (`brew install graphviz`, `apt install graphviz`). Without it the
command exits with code 1; the `mermaid` and `dot` text formats work anyway.
An edge to an unknown step exits with code 1. Cycles are drawn as they are.

#### Examples

```bash
geenii flow graph my_flow.yaml
```

```bash
geenii flow graph my_flow.yaml -o my_flow.svg
```

```bash
geenii flow graph my_flow.yaml -f dot | dot -Tpng -o my_flow.png
```

Mermaid output renders directly in GitHub and GitLab Markdown inside a
` ```mermaid ` block, and in the editor at <https://mermaid.live>. To turn it
into an image without Graphviz, use the Mermaid CLI:
`npx @mermaid-js/mermaid-cli -i flow.mmd -o flow.svg`.

```
$ geenii flow graph examples/flow_example.yaml
flowchart LR
    n0["step0<br/>(echo)"]
    n1["step1<br/>(read_http)"]
    n2["step2<br/>(execute_command)"]
    n3["step3<br/>(execute_script)"]
    n0 --> n1
    n1 --> n2
    n2 --> n3
```

### processors

```
geenii flow processors [--processor-module MODULE ...]
```

List the registered processor types (the values a step's `processor` field
can take) with the first line of their docstring. Use `-m` to include custom
processors from your own modules.

```
$ geenii flow processors
echo                 Returns the configured message, or the step input if no message is set
execute_command      Runs a command in a subprocess
execute_script       Runs a Python script in a separate interpreter process.
read_file            Reads a text file. JSON, TOML or lines are parsed into `data`; format "auto" picks by file extension.
read_http            Sends an HTTP request. `body` is sent as JSON; a JSON response is parsed into `data`.
```
