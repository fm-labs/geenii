# Flow: Step Pipelines

`geenii/flow/` runs steps as a directed acyclic graph (DAG). The steps are the
nodes, and **edges** (`from_step -> to_step`) define the order. A step's output
becomes the input of the steps after it, and a step's config can reference the
results of any step that ran before it. Flows are defined in Python or loaded
from a JSON or TOML file.

| Module | Contents |
|---|---|
| `geenii/flow/flow.py` | `Flow`, `FlowStep`, `FlowStepSpec`, `FlowContext`, results, step registry |
| `geenii/flow/steps/` | Built-in steps: `echo`, `execute_command`, `execute_script`, `read_http` |

A runnable example is in `src/xflow.py` (`uv run python src/xflow.py`), and a
file-based one is in `examples/flow_example.toml`.

Flows are **synchronous** and run in the calling thread. They are not wired
into the daemon, scheduler or CLI yet.

---

## Quick start

```python
import sys
from geenii.flow import Flow, FlowStepSpec

flow = Flow(
    name="demo",
    variables={"greeting": "hello"},
    steps=[
        FlowStepSpec(id="greet", type="echo", config={"message": "${vars.greeting}"}),
        FlowStepSpec(id="upper", type="execute_command",
                     config={"command": [sys.executable, "-c",
                                         "import sys; print(sys.argv[1].upper())",
                                         "${greet.message}"]}),
    ],
)

result = flow.run()
print(result.status)                    # "success"
print(result.get("upper").output)       # {"stdout": "HELLO\n", "stderr": "", "rc": 0}
print(result.output)                    # output of the last successful step
```

Steps can also be given as plain dicts (`{"id": ..., "type": ..., "config": ...}`)
or added later with `flow.add_step(...)`.

---

## Step specs

Each entry in a flow is a `FlowStepSpec`:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | `str` | required | Unique id within the flow; used in references and results |
| `type` | `str` | required | A registered step name (`"echo"`) or `"package.module:ClassName"` |
| `config` | `dict` | `{}` | Step settings; string values may contain `${...}` references |
| `on_error` | `"stop"` \| `"continue"` | `"stop"` | What happens when this step fails |
| `after` | `list[str]` (or one `str`) | `[]` | Ids of steps this step runs after; each adds an edge |

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
flow.add_edge("c", "d")          # also: add_edge(("c", "d")), add_edge(FlowEdge(...))

# inferred from `after`
flow.add_step(FlowStepSpec(id="report", type="echo", after=["left", "right"]))
```

`flow.edges` returns all edges: the explicit ones, then the ones inferred from
`after`. Duplicate edges are ignored.

**Without any edges, the steps are chained in the order they were added**
(`a -> b -> c ...`). This is the original sequential behavior. As soon as one
edge exists (explicit or from `after`), only the edges count. A step without
edges is then an independent root.

Order rules:

- Steps run **one at a time**, in topological order (`flow.execution_order()`).
  When several steps are ready, they run in the order they were added.
- A step that lists itself (`add_edge("a", "a")`) raises `FlowError` right away.
- An edge to an unknown step id, or a cycle, makes `run()` (and
  `execution_order()`) raise `FlowError` before any step runs. These are the
  only errors `run()` raises.

Example: a fan-out and a join (from `src/xflow.py`):

```
greet -> upper -> count -+-> stats -+-> summary
                         +-> http  -+
```

---

## Data between steps

There are two ways data moves through a flow:

1. **Input from predecessors.** The `input_data` that a step's `process()`
   receives depends on how many steps it runs after:

   | Predecessors | `input_data` |
   |---|---|
   | none (a root) | the value passed to `flow.run(input_data=...)` |
   | one | that step's output |
   | several | `{step_id: output, ...}`, in edge order |

   A predecessor that failed with `on_error="continue"` contributes `None`.
2. **References in config.** Before a step is created, its `config` is resolved
   against the run state.

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
- References don't add edges. A step that references `${a.x}` should run after
  `a` (directly or indirectly); otherwise whether `a` has run yet depends on
  insertion order.

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
Exceptions raised by a step are caught and recorded; they don't propagate out
of `run()`. An invalid graph raises `FlowError` before any step runs (see
[Edges and execution order](#edges-and-execution-order)).

`FlowResult`:

| Member | Meaning |
|---|---|
| `name` | Flow name |
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
  branches.
- `on_error="continue"`: the step is marked `"failed"` and the flow continues.
  Steps after it still run and get `None` for its output. The final flow
  status is still `"failed"`.
- A step can call `ctx.abort("reason")` to end the flow. The step is marked
  `"aborted"` with the reason as its error, the remaining steps are skipped,
  and the flow status is `"aborted"`.

### Events

Pass `on_event` to observe a run. It is called with a `StepEvent`
(`type`, `data`, `step_id`):

| Event type | When |
|---|---|
| `step.start` | Before a step runs; `data = {"type": ...}` |
| `step.end` | After a step; `data = {"status": ..., "error": ...}` |
| anything a step yields | e.g. `log` from the built-in steps; non-`StepEvent` values are wrapped as `data` |

Events are also logged at debug level on the `geenii.flow.flow.<flow name>`
logger.

---

## Loading flows from files

`Flow.from_file(path)` reads `.toml` or `.json`; `Flow.from_dict(data)` takes
the same structure:

```toml
name = "example"

# optional; edges can also come from `after` on the steps
edges = [
    { from_step = "greet", to_step = "list" },
]

[vars]
greeting = "hello"

[[steps]]
id = "greet"
type = "echo"
config = { message = "${vars.greeting}" }

[[steps]]
id = "list"
type = "execute_command"
on_error = "continue"
config = { command = ["docker", "container", "list", "--all"] }

[[steps]]
id = "report"
type = "echo"
after = ["greet", "list"]
```

```python
from geenii.flow import Flow

result = Flow.from_file("examples/flow_example.toml").run()
```

---

## Built-in steps

### `echo`

Returns `{"message": ...}`. It returns the configured `message`, or the step
input if no message is set. Useful for building values and in tests.

| Config | Default |
|---|---|
| `message` | `None` (use the step input) |

### `execute_command`

Runs a command with `subprocess.run` and waits for it to finish.

| Config | Default | Meaning |
|---|---|---|
| `command` | required | `str` or `list[str]` |
| `shell` | `false` | Run through the shell; a list command is joined with `shlex.join` |
| `cwd` | `None` | Working directory |
| `env` | `None` | Extra variables, merged over the current environment |
| `stdin` | `None` | Text sent to stdin |
| `timeout` | `None` | Seconds; on timeout the step fails |
| `check` | `false` | Fail the step on a non-zero exit code |

Without `shell`, a string command is split with `shlex.split`.
Output: `{"stdout", "stderr", "rc"}`.

### `execute_script`

Runs a Python script in a **separate interpreter** (`sys.executable -c`), so a
broken script can't affect the runner. The script is dedented, so indented
triple-quoted strings work. The step input is sent to the script as JSON on
stdin.

| Config | Default | Meaning |
|---|---|---|
| `script` | required | Python source |
| `args` | `[]` | Available as `sys.argv[1:]` |
| `cwd`, `env`, `timeout` | `None` | As for `execute_command` |
| `check` | `true` | Fail the step on a non-zero exit code |
| `json_output` | `false` | Parse stdout as JSON into `result` |

Output: `{"stdout", "stderr", "rc", "result"}`.

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

## Writing a step

Subclass `FlowStep` and register it:

```python
import pydantic
from geenii.flow import FlowStep, StepEvent, register_step


class GreetConfig(pydantic.BaseModel):
    name: str
    shout: bool = False


class GreetOutput(pydantic.BaseModel):
    text: str


@register_step("greet")
class GreetStep(FlowStep):
    config_model = GreetConfig      # optional: validates config into self.config
    output_model = GreetOutput      # optional: validates the returned output

    def process(self, input_data, ctx):
        text = f"hello {self.config.name}"
        yield StepEvent("log", text)        # progress events (optional)
        if not text:
            ctx.abort("nothing to say")     # stop the whole flow
        return GreetOutput(text=text.upper() if self.config.shout else text)
```

Rules for steps:

- `process(input_data, ctx)` is a generator. What it **yields** becomes an
  event; what it **returns** is the step output. A plain method that returns
  the output (no `yield`) also works.
- A new step instance is created for every run. Config references are resolved
  first, so `self.config` already holds the final values.
- Without `config_model`, `self.config` is the plain dict. Without
  `output_model`, the returned value is stored as is. It should be plain data
  (dicts, lists, scalars) so that later references can traverse it.
- Raise an exception to fail the step. Its `on_error` decides what happens
  next.
- `ctx` (`FlowContext`) gives access to `ctx.input`, `ctx.vars`,
  `ctx.results` (outputs by step id), `ctx.emit(type, data)`,
  `ctx.abort(reason)` and `ctx.logger`.

### Step types and lookup

- `@register_step("name")` adds the class to a module-level registry. The
  built-in steps register when `geenii.flow.steps` is imported, which
  `get_step_class()` does on first use. A custom step only needs its module
  to be imported before the flow runs.
- A `type` containing `:` (`"mypkg.steps:GreetStep"`) is imported with
  `importlib` and doesn't need to be registered. This is the way to use custom
  steps from flow files.
- An unknown type, or a class that isn't a `FlowStep`, fails the step with a
  `FlowError`.

---

## Testing

Tests are in `tests/geenii/flow/test_flow.py`:

```bash
uv run pytest tests/geenii/flow -q
```

`read_http` has a class attribute `transport` for tests. Set it to an
`httpx.MockTransport` to avoid network calls:

```python
monkeypatch.setattr(ReadHttpStep, "transport", httpx.MockTransport(handler))
```

---

## Not implemented yet

- A `geenii flow run <file>` CLI command.
- Async execution and integration with the daemon or scheduler.
- Parallel execution: independent branches still run one at a time.
- Conditional edges, loops and retries.
- Branch-local failure handling: with `on_error="stop"` a failure stops the
  whole flow, not just the steps that depend on the failed step.
- Inferring edges from `${...}` references.
- Streaming output from long-running commands; `execute_command` returns only
  when the process exits.
