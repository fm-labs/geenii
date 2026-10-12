# Flow: Step Pipelines

`geenii/flow/` runs steps as a directed acyclic graph (DAG). The steps are the
nodes, and **edges** (`from_step -> to_step`) define the order. A step's output
becomes the input of the steps after it, and a step's config can reference the
results of any step that ran before it. Flows are defined in Python or loaded
from a JSON or TOML file.

Two terms:

- A **step** is a node in the flow, defined by a `FlowStepSpec`: its id, its
  config, its edges and what happens when it fails.
- A **processor** is the class that handles a step: a `FlowProcessor`
  subclass, picked by the spec's `processor` field (e.g. `"echo"`). One
  processor type can handle many steps, and a new processor instance is
  created each time a step runs.

| Module | Contents |
|---|---|
| `geenii/flow/flow.py` | `Flow`, `FlowStepSpec`, `FlowProcessor`, `FlowContext`, results, processor registry |
| `geenii/flow/processor/` | Built-in processors: `echo`, `execute_command`, `execute_script`, `read_file`, `read_http` |

A runnable example is in `src/xflow.py` (`uv run python src/xflow.py`), and a
file-based one is in `examples/flow_example.toml`.

`run()` is **synchronous**: it returns when the flow is done. By default steps
run one at a time in the calling thread; with `max_workers > 1`, independent
steps run in parallel in a thread pool (see
[Parallel execution](#parallel-execution)). Flows are not wired into the
daemon or scheduler yet.

From the command line, use [`geenii flow`](../cli-reference/flow.md):
`geenii flow run FILE`, `geenii flow validate FILE`, `geenii flow graph FILE`
and `geenii flow processors`.

---

## Quick start

```python
import sys
from geenii.flow import Flow, FlowStepSpec

flow = Flow(
  name="demo",
  variables={"greeting": "hello"},
  steps=[
    FlowStepSpec(id="greet", processor="echo", config={"message": "${vars.greeting}"}),
    FlowStepSpec(id="upper", processor="execute_command", depends_on="greet",
                 config={"command": [sys.executable, "-c",
                                     "import sys; print(sys.argv[1].upper())",
                                     "${greet.message}"]}),
  ],
)

result = flow.run()
print(result.status)  # "success"
print(result.get("upper").output)  # {"stdout": "HELLO\n", "stderr": "", "rc": 0}
print(result.output)  # output of the last successful step
```

Steps can also be given as plain dicts (`{"id": ..., "processor": ..., "config": ...}`)
or added later with `flow.add_step(...)`.

---

## Step specs

Each entry in a flow is a `FlowStepSpec`:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | `str` | required | Unique id within the flow; used in references and results |
| `processor` | `str` | required | The processor that handles the step: a registered name (`"echo"`) or `"package.module:ClassName"` |
| `config` | `dict` | `{}` | Settings passed to the processor; string values may contain `${...}` references |
| `on_error` | `"stop"` \| `"continue"` | `"stop"` | What happens when this step fails |
| `depends_on` | `list[str]` (or one `str`) | `[]` | Ids of steps this step depends on (runs after); each adds an edge |

Step ids must be unique and cannot be `input` or `vars` (these are reserved for
references). Both rules are checked when the step is added, and violations
raise `FlowError`.

---

## Edges and execution order

An edge `FlowEdge(from_step="a", to_step="b")` means "`b` runs after `a`, and
gets `a`'s output". There are two ways to add edges, and they can be mixed:

```python
from geenii.flow import Flow, FlowStepSpec

# explicit edges
flow = Flow("t", steps=[...], edges=[("a", "b"), {"from_step": "b", "to_step": "c"}])
flow.add_edge("c", "d")  # also: add_edge(("c", "d")), add_edge(FlowEdge(...))

# inferred from `depends_on`
flow.add_step(FlowStepSpec(id="report", processor="echo", depends_on=["left", "right"]))
```

`flow.edges` returns all edges: the explicit ones, then the ones inferred from
`depends_on`. Duplicate edges are ignored.

**Steps are never wired automatically.** A step without edges is an
independent root: it gets the flow input and may run in parallel with other
steps. To pass a step's output on, or to make sure a step has finished before
another one references its results with `${...}`, set `depends_on` (or add an
edge).

Order rules:

- A step is **ready** once all the steps it runs after have finished
  (succeeded, or failed with `on_error="continue"`).
- With the default `max_workers=1`, steps run one at a time in topological
  order (`flow.execution_order()`). When several steps are ready, they run in
  the order they were added.
- With `max_workers > 1`, ready steps start right away, up to `max_workers`
  at a time (see [Parallel execution](#parallel-execution)).
- A step that lists itself (`add_edge("a", "a")`) raises `FlowError` right away.
- An edge to an unknown step id, or a cycle, makes `run()` (and
  `execution_order()`) raise `FlowError` before any step runs. These are the
  only errors `run()` raises.

Example: a fan-out and a join (from `src/xflow.py`):

```
greet -> upper -> count -+-> stats -+-> summary
                         +-> http  -+
```

### Drawing the graph

`flow.to_mermaid()` and `flow.to_dot()` return the graph as Mermaid flowchart
or Graphviz DOT text. Nodes are labelled with the step id and processor, and
`flow.edges` become the arrows. Both take a layout direction (`"LR"` by default, or `"TB"`, `"RL"`,
`"BT"`). They raise `FlowError` for an edge to an unknown step; cycles are
drawn as they are.

```python
print(flow.to_mermaid())
# flowchart LR
#     n0["greet<br/>(echo)"]
#     n1["upper<br/>(execute_command)"]
#     n0 --> n1
```

Mermaid node ids are generated (`n0`, `n1`, ...) in step order, so any step
id is safe to use. To render an image from the command line, use
[`geenii flow graph`](../cli-reference/flow.md#graph).

---

## Parallel execution

Set `max_workers` to let independent steps run at the same time:

```python
flow = Flow("t", steps=[...], max_workers=4)   # default for this flow
result = flow.run()
result = flow.run(max_workers=1)               # override for one run
```

In a flow file, set `max_workers = 4` at the top level. Values below 1 make
`run()` raise `FlowError`.

How it works:

- `max_workers=1` (the default) runs every step in the calling thread, exactly
  as before.
- With `max_workers > 1`, steps run in a `ThreadPoolExecutor`, in threads
  named `flow-<flow name>_N`. The runner thread starts every ready step (in
  insertion order) while fewer than `max_workers` are running, and starts
  more steps as running ones finish.
- Threads suit the built-in processors, which mostly wait on subprocesses and
  HTTP. CPU-heavy Python code in a processor doesn't run in parallel because of
  the GIL; use `execute_script` to run it in its own process.
- `FlowResult.steps` is always in execution order, not completion order, so
  results look the same whichever thread finished first.

Failures and aborts while steps run in parallel:

- When a step fails with `on_error="stop"` or aborts, no new steps start.
  Steps that are **already running keep running to the end**, and their
  results are recorded as usual. The steps that never started are marked
  `"skipped"`.
- A running step can check `ctx.stopping` (it becomes `True` once the flow is
  stopping) to finish early. There is no way to kill a running step from the
  outside.
- If an aborted step and a failed step both happen in one run, the flow
  status is `"aborted"`.

Thread safety for processor authors:

- `on_event` callbacks are called one at a time (under a lock), so a
  callback doesn't have to be thread-safe. A slow callback slows down every
  step that emits events.
- `ctx.results` is only written by the runner thread, after a step finishes.
- `ctx.vars` is shared between steps. Changing it from a processor isn't
  synchronized.

---

## Data between steps

There are two ways data moves through a flow:

1. **Input from predecessors.** The `input_data` that a step's processor
   receives in `process()` depends on how many steps it runs after:

   | Predecessors | `input_data` |
   |---|---|
   | none (a root) | the value passed to `flow.run(input_data=...)` |
   | one | that step's output |
   | several | `{step_id: output, ...}`, in edge order |

   A predecessor that failed with `on_error="continue"` contributes `None`.
2. **References in config.** Before a step's processor is created, the step's
   `config` is resolved against the run state.

### Reference syntax

| Reference | Resolves to |
|---|---|
| `${input}` | The value passed to `flow.run(input_data=...)` |
| `${vars.name}` | A flow variable (`Flow(variables=...)` or `[vars]` in a file) |
| `${step0}` | The whole output of step `step0` |
| `${step0.stdout}` | A field of that output |
| `${step0.items.0.name}` | Paths go through dict keys, list indexes and attributes |
| `$${...}` | A literal `${...}` |

Resolution rules:

- A string that is **exactly one reference** gets the raw value, keeping its
  type: `"${a.items}"` becomes a list.
- A string with **other text around a reference** is interpolated as text.
  Strings are inserted as they are, and other values are inserted as JSON.
- References are resolved inside nested dicts and lists.
- A reference to an unknown step or a missing field fails the step with a
  `FlowError`.
- Only steps that have already succeeded can be referenced. Outputs are
  stored as plain data, so pydantic outputs are dumped to dicts.
- References don't add edges. A step that references `${a.x}` must depend on
  `a` (directly or indirectly); otherwise whether `a` has run yet depends on
  insertion order and `max_workers`.

`flow.check_references()` checks this without running the flow. It returns a
warning for each reference to a step that the referencing step doesn't depend
on, to the step itself, or to an unknown name. `${input}`, `${vars...}` and
`$${...}` escapes are not checked. `run()` logs these warnings on the
`geenii.flow.flow` logger and then runs the flow anyway, and
`geenii flow validate` prints them. `flow.ancestors()` returns, for each step,
the ids of all steps it depends on directly or indirectly.

> **Shell commands:** with `execute_command` and `shell: true`, interpolated
> values are pasted into the command line as text. A trailing newline (common
> in `stdout`) splits the command, and an untrusted value can inject shell
> syntax. Prefer a list `command` with `shell: false` and pass values as
> separate arguments.

---

## Running and results

```python
result = flow.run(input_data=None, on_event=None)
```

`run()` executes the steps in execution order and returns a `FlowResult`.
Exceptions raised by a processor are caught and recorded; they don't propagate out
of `run()`. An invalid graph raises `FlowError` before any step runs (see
[Edges and execution order](#edges-and-execution-order)).

Each run has a **context id**, `FlowContext.id`. By default it is a random
UUID (32 hex characters), generated for every run. Pass
`run(context_id="...")` to use your own, e.g. to match a run with a job in
another system. Processors can read it as `ctx.id`.

`FlowResult`:

| Member | Meaning |
|---|---|
| `name` | Flow name |
| `context_id` | Context id of the run |
| `status` | `"success"`, `"failed"` (any step failed) or `"aborted"` |
| `steps` | `list[StepResult]`, one per step in the flow, in execution order |
| `output` | Output of the last successful step in execution order |
| `get(step_id)` | The `StepResult` for a step, or `None` |

`StepResult` has `step_id`, `status` (`"success"`, `"failed"`, `"aborted"`,
`"skipped"`), `output`, `error` (`"ExceptionType: message"`) and `duration` in
seconds.

### Errors and aborting

- `on_error="stop"` (the default): the flow status becomes `"failed"` and all
  remaining steps are marked `"skipped"`, including steps on independent
  branches. With parallel execution, steps that are already running finish
  first.
- `on_error="continue"`: the step is marked `"failed"` and the flow continues.
  Steps after it still run and get `None` for its output. The final flow
  status is still `"failed"`.
- A processor can call `ctx.abort("reason")` to end the flow. The step is marked
  `"aborted"` with the reason as its error, the remaining steps are skipped,
  and the flow status is `"aborted"`.

### Events

Pass `on_event` to observe a run. It is called with a `StepEvent`
(`type`, `data`, `step_id`):

| Event type | When |
|---|---|
| `step.start` | Before a step runs; `data = {"processor": <processor name>}` |
| `step.end` | After a step; `data = {"status": ..., "error": ...}` |
| anything a processor yields | e.g. `log` from the built-in processors; non-`StepEvent` values are wrapped as `data` |

Events are also logged at debug level on the `geenii.flow.flow.<flow name>`
logger.

---

## Loading flows from files

`Flow.from_file(path)` reads `.toml` or `.json`; `Flow.from_dict(data)` takes
the same structure:

```toml
name = "example"
max_workers = 2   # optional, default 1

# optional; edges can also come from `depends_on` on the steps
edges = [
    { from_step = "greet", to_step = "list" },
]

[vars]
greeting = "hello"

[[steps]]
id = "greet"
processor = "echo"
config = { message = "${vars.greeting}" }

[[steps]]
id = "list"
processor = "execute_command"
on_error = "continue"
config = { command = ["docker", "container", "list", "--all"] }

[[steps]]
id = "report"
processor = "echo"
depends_on = ["greet", "list"]
```

```python
from geenii.flow import Flow

result = Flow.from_file("examples/flow_example.toml").run()
```

### Saving flows

`flow.to_dict()` returns the flow definition in the same structure, and
`flow.to_json()` returns it as a JSON string. `flow.to_file(path)` writes it to
a `.json` or `.toml` file that `from_file()` can read again. Step fields with
default values are left out, and only explicit edges are written (edges from
`depends_on` stay on the steps). TOML can't store `None` values, so use `.json` for
flows whose config contains `None`.

To save a run together with its results, see [Snapshots](#snapshots).

### Snapshots

`run(snapshot=...)` saves the state of the run as a `FlowSnapshot`. Pass a
file path to write it as JSON, or a callback to get the `FlowSnapshot` object
itself:

```python
result = flow.run(input_data={"n": 1}, snapshot="run.json")

snap = FlowSnapshot.load("run.json")
snap.status            # "success"
snap.get("a").output   # output of step "a"
snap.to_flow()         # the Flow again
```

A snapshot is taken when the run starts, after steps finish, and once more
when the run ends. Each snapshot replaces the last one. The file is written to
a temporary file and then renamed, so another process reading it never sees a
half-written file. The callback is called from the thread that runs the flow.
An error while saving is logged as a warning and doesn't stop the flow.

`FlowSnapshot` fields:

| Field | Meaning |
|---|---|
| `context_id` | Context id of the run |
| `flow` | The flow definition (`Flow.to_dict()`) |
| `input` | The flow input; a value that isn't JSON serializable is written as `str()` |
| `status` | `"running"` until the run ends, then the flow status |
| `started_at`, `updated_at` | UTC timestamps |
| `steps` | `StepResult`s of the finished steps in execution order; at the end, skipped steps too |
| `running` | Ids of steps that were running at the time of the snapshot |
| `pending` | Ids of steps that hadn't started yet |

Snapshots are taken right after steps finish, before the next steps start.
So with parallel execution, steps that are about to start are listed in
`pending`.

Without snapshots, the run's results are still in the returned `FlowResult`,
a pydantic model: `result.model_dump_json(indent=2)` gives the status, outputs,
errors and durations of all steps, but not the flow definition or the input.
This is what `geenii flow run --json` prints.

---

## Built-in processors

### `echo`

Returns `{"message": ...}`. It returns the configured `message`, or the step
input if no message is set. Useful for building values and in tests.

| Config | Default |
|---|---|
| `message` | `None` (use the step input) |

### `execute_command`

Runs a command in a subprocess and waits for it to finish. While it runs, each
line of output is emitted as a `stdout` or `stderr` event (without the line
ending), so `geenii flow run` prints it as it arrives. A partial line without a
newline is emitted only when the newline or the end of the output arrives. A
program that buffers its output when it isn't writing to a terminal may emit
lines only when its buffer fills or the program exits.

| Config | Default | Meaning |
|---|---|---|
| `command` | required | `str` or `list[str]` |
| `shell` | `false` | Run through the shell; a list command is joined with `shlex.join` |
| `cwd` | `None` | Working directory |
| `env` | `None` | Extra variables, merged over the current environment |
| `stdin` | `None` | Text sent to stdin |
| `timeout` | `None` | Seconds; on timeout the process is killed and the step fails |
| `check` | `false` | Fail the step on a non-zero exit code |

Without `shell`, a string command is split with `shlex.split`.
Output: `{"stdout", "stderr", "rc"}`.

### `execute_script`

Runs a Python script in a **separate interpreter** (`sys.executable -u -c`), so a
broken script can't affect the runner. The script is dedented, so indented
triple-quoted strings work. The step input is sent to the script as JSON on
stdin. Output is unbuffered and streamed as events, as for `execute_command`.

| Config | Default | Meaning |
|---|---|---|
| `script` | required | Python source |
| `args` | `[]` | Available as `sys.argv[1:]` |
| `cwd`, `env`, `timeout` | `None` | As for `execute_command` |
| `check` | `true` | Fail the step on a non-zero exit code |
| `json_output` | `false` | Parse stdout as JSON into `result` |

Output: `{"stdout", "stderr", "rc", "result"}`.

### `read_file`

Reads a text file.

| Config | Default | Meaning |
|---|---|---|
| `path` | required | File path; `~` is expanded, and a relative path is relative to the current working directory |
| `format` | `"auto"` | How to parse the text into `data`: `"text"` (no parsing), `"json"`, `"toml"`, `"lines"` (a list of lines without line endings), or `"auto"`: `json` for `.json`, `toml` for `.toml`, otherwise `text` |
| `encoding` | `"utf-8"` | Text encoding |
| `max_size` | `None` | Fail the step if the file is larger than this many bytes |

Output: `{"path", "size", "text", "data"}`. `path` is the resolved absolute
path, and `size` is in bytes. `data` is `None` for the `text` format. A
missing file, a file that can't be decoded, or invalid JSON/TOML fails the
step.

### `read_http`

Sends an HTTP request with `httpx`.

| Config | Default | Meaning |
|---|---|---|
| `url` | required | |
| `method` | `"GET"` | |
| `headers`, `params` | `{}` | |
| `body` | `None` | Sent as JSON when set |
| `timeout` | `30.0` | Seconds |
| `raise_for_status` | `true` | Fail the step on 4xx/5xx responses |

Output: `{"status", "headers", "text", "data"}`. `data` is the parsed body when
the response content type is JSON, otherwise `None`.

---

## Writing a processor

Subclass `FlowProcessor` and register it under a name. Steps then use it with
`processor="greet"`:

```python
import pydantic
from geenii.flow import FlowProcessor, StepEvent, register_processor


class GreetConfig(pydantic.BaseModel):
  name: str
  shout: bool = False


class GreetOutput(pydantic.BaseModel):
  text: str


@register_processor("greet")
class GreetProcessor(FlowProcessor):
  config_model = GreetConfig  # optional: validates config into self.config
  output_model = GreetOutput  # optional: validates the returned output

  def process(self, input_data, ctx):
    text = f"hello {self.config.name}"
    yield StepEvent("log", text)  # progress events (optional)
    if not text:
      ctx.abort("nothing to say")  # stop the whole flow
    return GreetOutput(text=text.upper() if self.config.shout else text)
```

Rules for processors:

- `process(input_data, ctx)` is a generator. What it **yields** becomes an
  event; what it **returns** is the step's output. A plain method that returns
  the output (no `yield`) also works.
- A new processor instance is created each time a step runs, with the step's
  config. Config references are resolved first, so `self.config` already holds
  the final values.
- Without `config_model`, `self.config` is the plain dict. Without
  `output_model`, the returned value is stored as is. It should be plain data
  (dicts, lists, scalars) so that later references can traverse it.
- Raise an exception to fail the step. Its `on_error` decides what happens
  next.
- `ctx` (`FlowContext`) gives access to `ctx.id` (the context id), `ctx.input`, `ctx.vars`,
  `ctx.results` (outputs by step id), `ctx.emit(type, data)`,
  `ctx.abort(reason)`, `ctx.stopping` and `ctx.logger`.
- A processor may run in a worker thread (with `max_workers > 1`), so don't
  rely on thread-local state or signal handlers. Long-running processors should
  check `ctx.stopping` now and then.

### Processor types and lookup

- `@register_processor("name")` adds the class to a module-level registry. The
  built-in processors register when `geenii.flow.processor` is imported, which
  `get_step_processor_class()` and `list_processor_types()` do on first use. A
  custom processor only needs its module to be imported before the flow runs
  (on the command line: `--processor-module`).
- A `processor` value containing `:` (`"mypkg.processors:GreetProcessor"`) is
  imported with `importlib` and doesn't need to be registered. This is the way
  to use custom processors from flow files without `--processor-module`.
- An unknown processor, or a class that isn't a `FlowProcessor`, fails the step
  with a `FlowError`.

---

## Testing

Tests are in `tests/geenii/flow/test_flow.py` and
`tests/geenii/flow/test_flow_cli.py`:

```bash
uv run pytest tests/geenii/flow -q
```

`ReadHttpProcessor` has a class attribute `transport` for tests. Set it to an
`httpx.MockTransport` to avoid network calls:

```python
monkeypatch.setattr(ReadHttpProcessor, "transport", httpx.MockTransport(handler))
```

---

## Not implemented yet

- Async execution and integration with the daemon or scheduler.
- Process-based parallelism, and cancelling a running step.
- Conditional edges, loops and retries.
- Branch-local failure handling: with `on_error="stop"` a failure stops the
  whole flow, not just the steps that depend on the failed step.
- Inferring edges from `${...}` references.
