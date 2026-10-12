"""
Flow: run steps as a DAG, passing each step's output to the steps after it.

A flow is a set of FlowStepSpecs (the nodes) and FlowEdges (the order). Each
spec names a processor (a registered name like "echo", or
"package.module:ClassName") that handles the step, a unique id and a config. Edges are added with
Flow.add_edge() or inferred from a step's ``after`` list. A flow without any
edges runs its steps in the order they were added.

A step starts once all its predecessors have finished. With max_workers=1 (the
default) steps run one at a time in the calling thread, in topological order
(ties keep insertion order). With max_workers > 1, independent steps run in
parallel in a thread pool. A step's input is the flow input if it has no predecessors, the predecessor's
output if it has one, or a dict {step_id: output} if it has several.

String values in a step config may reference earlier results with ``${...}``:

- ``${input}``            the flow input
- ``${vars.name}``        a flow variable
- ``${step0}``            the whole output of step "step0"
- ``${step0.stdout}``     a field of it (dict keys, attributes and list indexes)

A string that is exactly one reference gets the raw value, otherwise the
references are interpolated as text. Use ``$${`` for a literal ``${``.
"""
import importlib
import inspect
import json
import logging
import re
import threading
import time
import tomllib
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, ClassVar, Generator, Literal

import pydantic

logger = logging.getLogger(__name__)

RESERVED_IDS = {"input", "vars"}


class FlowError(Exception):
    pass


class FlowAborted(Exception):
    """Raised by FlowContext.abort() to stop the flow."""


class FlowStepSpec(pydantic.BaseModel):
    id: str
    processor: str
    config: dict[str, Any] = {}
    on_error: Literal["stop", "continue"] = "stop"
    # ids of steps this step runs after; each one adds an edge (after_id -> id)
    after: list[str] = []

    @pydantic.field_validator("after", mode="before")
    @classmethod
    def _after_as_list(cls, v: Any) -> Any:
        return [v] if isinstance(v, str) else v


class FlowEdge(pydantic.BaseModel):
    from_step: str
    to_step: str


@dataclass
class StepEvent:
    type: str
    data: Any = None
    step_id: str | None = None


class StepResult(pydantic.BaseModel):
    step_id: str
    status: Literal["success", "failed", "aborted", "skipped"]
    output: Any = None
    error: str | None = None
    duration: float = 0.0


class FlowResult(pydantic.BaseModel):
    name: str
    status: Literal["success", "failed", "aborted"]
    steps: list[StepResult]

    @property
    def output(self) -> Any:
        """Output of the last successful step"""
        for r in reversed(self.steps):
            if r.status == "success":
                return r.output
        return None

    def get(self, step_id: str) -> StepResult | None:
        return next((r for r in self.steps if r.step_id == step_id), None)


class FlowContext:
    """
    Run state shared by all steps of one flow run.

    With parallel execution, steps call into the context from worker threads:
    results are only written by the runner thread, and events are delivered
    to on_event one at a time.
    """

    def __init__(self, flow_name: str, input_data: Any = None, variables: dict | None = None,
                 on_event: Callable[[StepEvent], None] | None = None):
        self.flow_name = flow_name
        self.input = input_data
        self.vars = dict(variables or {})
        self.results: dict[str, Any] = {}
        self.logger = logging.getLogger(f"{__name__}.{flow_name}")
        self._on_event = on_event
        self._event_lock = threading.RLock()
        self._stopping = threading.Event()

    @property
    def stopping(self) -> bool:
        """True once the flow is stopping (a step failed or aborted); long-running steps may check it"""
        return self._stopping.is_set()

    def emit(self, event_type: str, data: Any = None, step_id: str | None = None):
        self._emit(StepEvent(type=event_type, data=data, step_id=step_id))

    def _emit(self, event: StepEvent):
        self.logger.debug("event %s [%s]: %s", event.type, event.step_id, event.data)
        if self._on_event:
            with self._event_lock:
                self._on_event(event)

    def abort(self, reason: str = "aborted"):
        raise FlowAborted(reason)

    def lookup(self, ref: str) -> Any:
        """Resolve a dotted reference like 'step0.stdout' or 'vars.name'"""
        head, *path = ref.strip().split(".")
        if head == "input":
            value = self.input
        elif head == "vars":
            value = self.vars
        elif head in self.results:
            value = self.results[head]
        else:
            raise FlowError(f"Unknown reference '${{{ref}}}'")
        for part in path:
            value = _get_item(value, part, ref)
        return value

    def resolve(self, value: Any) -> Any:
        """Recursively resolve ${...} references in strings, dicts and lists"""
        if isinstance(value, str):
            return self._resolve_str(value)
        if isinstance(value, dict):
            return {k: self.resolve(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return type(value)(self.resolve(v) for v in value)
        return value

    def _resolve_str(self, s: str) -> Any:
        m = _REF_FULL.fullmatch(s)
        if m:
            return self.lookup(m.group(1))

        def repl(m: re.Match) -> str:
            if m.group(0).startswith("$$"):
                return m.group(0)[1:]
            value = self.lookup(m.group(1))
            return value if isinstance(value, str) else json.dumps(value, default=str)

        return _REF.sub(repl, s)


_REF = re.compile(r"\$?\$\{([^}]+)\}")
_REF_FULL = re.compile(r"\$\{([^}]+)\}")


def _get_item(value: Any, key: str, ref: str) -> Any:
    try:
        if isinstance(value, dict):
            return value[key]
        if isinstance(value, (list, tuple)):
            return value[int(key)]
        return getattr(value, key)
    except (KeyError, IndexError, ValueError, AttributeError):
        raise FlowError(f"Cannot resolve '{key}' in reference '${{{ref}}}'") from None


class FlowProcessor:
    """
    Base class for processing steps.

    Subclasses implement process() as a generator: yield StepEvents (or any
    value, which is wrapped as a "data" event) while working, and return the
    step output. A plain (non-generator) process() returning the output works too.
    """

    type_name: ClassVar[str | None] = None
    config_model: ClassVar[type[pydantic.BaseModel] | None] = None
    output_model: ClassVar[type[pydantic.BaseModel] | None] = None

    def __init__(self, config: dict | None = None):
        config = config or {}
        self.config = self.config_model.model_validate(config) if self.config_model else config

    def __str__(self) -> str:
        return f"{self.__class__.__name__}({self.config})"

    def process(self, input_data: Any, ctx: FlowContext) -> Generator[Any, None, Any]:
        raise NotImplementedError
        yield  # pragma: no cover


_PROCESSOR_REGISTRY: dict[str, type[FlowProcessor]] = {}


def register_processor(name: str):
    """Class decorator registering a processor type under a short name"""
    def decorator(cls: type[FlowProcessor]) -> type[FlowProcessor]:
        cls.type_name = name
        _PROCESSOR_REGISTRY[name] = cls
        return cls
    return decorator


def list_processor_types() -> dict[str, type[FlowProcessor]]:
    """All registered processor types by name, including the built-in processors"""
    import geenii.flow.processor  # noqa: F401 - registers the built-in processors
    return dict(sorted(_PROCESSOR_REGISTRY.items()))


def get_step_processor_class(processor: str) -> type[FlowProcessor]:
    if ":" in processor:
        module_name, class_name = processor.split(":", 1)
        cls = getattr(importlib.import_module(module_name), class_name, None)
        if cls is None:
            raise FlowError(f"Processor class '{class_name}' not found in '{module_name}'")
    else:
        import geenii.flow.processor  # noqa: F401 - registers the built-in processors
        cls = _PROCESSOR_REGISTRY.get(processor)
        if cls is None:
            raise FlowError(f"Unknown processor type '{processor}'")
    if not (inspect.isclass(cls) and issubclass(cls, FlowProcessor)):
        raise FlowError(f"'{processor}' is not a FlowProcessor")
    return cls


class Flow:
    """
    Assembles the steps to a workflow
    """

    def __init__(self, name: str, steps: list[FlowStepSpec | dict] | None = None,
                 edges: list[FlowEdge | dict | tuple[str, str]] | None = None, variables: dict | None = None,
                 max_workers: int = 1):
        self.name = name
        self.steps: list[FlowStepSpec] = []
        self._edges: list[FlowEdge] = []
        self.variables = dict(variables or {})
        # number of steps that may run at the same time; 1 runs them sequentially in the calling thread
        self.max_workers = max_workers
        for step in steps or []:
            self.add_step(step)
        for edge in edges or []:
            self.add_edge(edge)

    def add_step(self, step: FlowStepSpec | dict) -> FlowStepSpec:
        if isinstance(step, dict):
            step = FlowStepSpec.model_validate(step)
        if step.id in RESERVED_IDS:
            raise FlowError(f"Step id '{step.id}' is reserved")
        if any(s.id == step.id for s in self.steps):
            raise FlowError(f"Duplicate step id '{step.id}'")
        self.steps.append(step)
        return step

    def add_edge(self, edge: FlowEdge | dict | tuple[str, str] | str, to_step: str | None = None) -> FlowEdge:
        """Add an edge: add_edge("a", "b"), add_edge(("a", "b")) or add_edge(FlowEdge(...))"""
        if isinstance(edge, str):
            edge = FlowEdge(from_step=edge, to_step=to_step)
        elif isinstance(edge, (tuple, list)):
            edge = FlowEdge(from_step=edge[0], to_step=edge[1])
        elif isinstance(edge, dict):
            edge = FlowEdge.model_validate(edge)
        if edge.from_step == edge.to_step:
            raise FlowError(f"Step '{edge.from_step}' cannot run after itself")
        if edge not in self._edges:
            self._edges.append(edge)
        return edge

    @property
    def edges(self) -> list[FlowEdge]:
        """
        All edges: explicit ones plus those inferred from each step's `after`.
        Without any edges, the steps are chained in the order they were added.
        """
        edges = list(self._edges)
        for step in self.steps:
            for after in step.after:
                edge = FlowEdge(from_step=after, to_step=step.id)
                if edge not in edges:
                    edges.append(edge)
        if not edges:
            edges = [FlowEdge(from_step=a.id, to_step=b.id) for a, b in zip(self.steps, self.steps[1:])]
        return edges

    def predecessors(self) -> dict[str, list[str]]:
        """Map of step id -> ids of the steps it runs after (in edge order)"""
        ids = {s.id for s in self.steps}
        preds: dict[str, list[str]] = {s.id: [] for s in self.steps}
        for e in self.edges:
            for step_id in (e.from_step, e.to_step):
                if step_id not in ids:
                    raise FlowError(f"Edge {e.from_step} -> {e.to_step}: unknown step '{step_id}'")
            preds[e.to_step].append(e.from_step)
        return preds

    def execution_order(self) -> list[FlowStepSpec]:
        """Topological order of the steps; ties keep insertion order. Raises FlowError on cycles."""
        preds = self.predecessors()
        done: set[str] = set()
        order: list[FlowStepSpec] = []
        remaining = list(self.steps)
        while remaining:
            ready = next((s for s in remaining if all(p in done for p in preds[s.id])), None)
            if ready is None:
                raise FlowError(f"Cycle between steps: {', '.join(s.id for s in remaining)}")
            remaining.remove(ready)
            done.add(ready.id)
            order.append(ready)
        return order

    def to_mermaid(self, direction: str = "LR") -> str:
        """
        The flow graph as a Mermaid flowchart. Nodes show the step id and type.
        Raises FlowError if an edge references an unknown step; cycles are drawn as they are.
        """
        self.predecessors()  # validates the edges
        node = {s.id: f"n{i}" for i, s in enumerate(self.steps)}

        def label(text: str) -> str:
            return text.replace('"', "#quot;")

        lines = [f"flowchart {direction}"]
        for s in self.steps:
            lines.append(f'    {node[s.id]}["{label(s.id)}<br/>({label(s.processor)})"]')
        for e in self.edges:
            lines.append(f"    {node[e.from_step]} --> {node[e.to_step]}")
        return "\n".join(lines) + "\n"

    def to_dot(self, direction: str = "LR") -> str:
        """
        The flow graph in Graphviz DOT format. Nodes show the step id and type.
        Raises FlowError if an edge references an unknown step; cycles are drawn as they are.
        """
        self.predecessors()  # validates the edges

        def esc(text: str) -> str:
            return text.replace("\\", "\\\\").replace('"', '\\"')

        def quote(text: str) -> str:
            return f'"{esc(text)}"'

        lines = [
            f"digraph {quote(self.name)} {{",
            f"    rankdir={direction};",
            '    node [shape=box, style=rounded, fontname="Helvetica"];',
        ]
        for s in self.steps:
            lines.append(f'    {quote(s.id)} [label="{esc(s.id)}\\n{esc(s.processor)}"];')
        for e in self.edges:
            lines.append(f"    {quote(e.from_step)} -> {quote(e.to_step)};")
        lines.append("}")
        return "\n".join(lines) + "\n"

    @classmethod
    def from_dict(cls, data: dict) -> "Flow":
        return cls(name=data["name"], steps=data.get("steps", []), edges=data.get("edges"),
                   variables=data.get("vars"), max_workers=data.get("max_workers", 1))

    @classmethod
    def from_file(cls, path: str | Path) -> "Flow":
        """Load a flow from a .json or .toml file"""
        path = Path(path)
        if path.suffix == ".toml":
            data = tomllib.loads(path.read_text())
        elif path.suffix == ".json":
            data = json.loads(path.read_text())
        else:
            raise FlowError(f"Unsupported flow file type '{path.suffix}'")
        return cls.from_dict(data)

    def run(self, input_data: Any = None, on_event: Callable[[StepEvent], None] | None = None,
            max_workers: int | None = None) -> FlowResult:
        """
        Run the flow. max_workers overrides Flow.max_workers for this run.
        Raises FlowError for an invalid graph (unknown step in an edge, cycle) or max_workers < 1.
        """
        workers = self.max_workers if max_workers is None else max_workers
        if workers < 1:
            raise FlowError(f"max_workers must be at least 1, got {workers}")
        order = self.execution_order()
        preds = self.predecessors()
        ctx = FlowContext(self.name, input_data=input_data, variables=self.variables, on_event=on_event)
        results: dict[str, StepResult] = {}
        # outputs of finished steps; a failed step with on_error="continue" contributes None
        outputs: dict[str, Any] = {}
        pending = list(order)
        running: dict[Future, FlowStepSpec] = {}
        status = "success"

        executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix=f"flow-{self.name}") \
            if workers > 1 else _InlineExecutor()
        try:
            while True:
                # start every ready step (all predecessors finished), in execution order
                if not ctx.stopping:
                    for spec in list(pending):
                        if len(running) >= workers:
                            break
                        if all(p in results for p in preds[spec.id]):
                            pending.remove(spec)
                            step_input = _step_input(preds[spec.id], outputs, input_data)
                            running[executor.submit(self._execute_step, spec, step_input, ctx)] = spec
                if not running:
                    break

                done, _ = wait(running, return_when=FIRST_COMPLETED)
                for future in sorted(done, key=lambda f: order.index(running[f])):
                    spec = running.pop(future)
                    result = future.result()
                    results[spec.id] = result
                    outputs[spec.id] = result.output
                    if result.status == "success":
                        ctx.results[spec.id] = result.output
                    elif result.status == "aborted":
                        status = "aborted"
                        ctx._stopping.set()
                    else:
                        if status != "aborted":
                            status = "failed"
                        if spec.on_error == "stop":
                            ctx._stopping.set()
        finally:
            ctx._stopping.set()
            executor.shutdown(wait=True, cancel_futures=True)

        for spec in pending:
            results[spec.id] = StepResult(step_id=spec.id, status="skipped")
        return FlowResult(name=self.name, status=status, steps=[results[s.id] for s in order])

    def _execute_step(self, spec: FlowStepSpec, input_data: Any, ctx: FlowContext) -> StepResult:
        ctx.emit("step.start", {"processor": spec.processor}, step_id=spec.id)
        started = time.monotonic()
        try:
            step = get_step_processor_class(spec.processor)(config=ctx.resolve(spec.config))
            output = self._drive(step, spec, input_data, ctx)
            output = _dump(step.output_model.model_validate(output) if step.output_model else output)
            result = StepResult(step_id=spec.id, status="success", output=output)
        except FlowAborted as e:
            result = StepResult(step_id=spec.id, status="aborted", error=str(e))
        except Exception as e:
            logger.warning("Step '%s' failed: %s", spec.id, e)
            result = StepResult(step_id=spec.id, status="failed", error=f"{type(e).__name__}: {e}")
        result.duration = time.monotonic() - started
        ctx.emit("step.end", {"status": result.status, "error": result.error}, step_id=spec.id)
        return result

    @staticmethod
    def _drive(step: FlowProcessor, spec: FlowStepSpec, input_data: Any, ctx: FlowContext) -> Any:
        gen = step.process(input_data, ctx)
        if not inspect.isgenerator(gen):
            return gen
        while True:
            try:
                event = next(gen)
            except StopIteration as stop:
                return stop.value
            if not isinstance(event, StepEvent):
                event = StepEvent(type="data", data=event)
            event.step_id = spec.id
            ctx._emit(event)


def _step_input(step_preds: list[str], outputs: dict[str, Any], flow_input: Any) -> Any:
    if not step_preds:
        return flow_input
    if len(step_preds) == 1:
        return outputs[step_preds[0]]
    return {p: outputs[p] for p in step_preds}


class _InlineExecutor:
    """Runs submitted calls immediately in the calling thread (max_workers=1)"""

    def submit(self, fn: Callable, *args: Any) -> Future:
        future: Future = Future()
        try:
            future.set_result(fn(*args))
        except BaseException as e:
            future.set_exception(e)
        return future

    def shutdown(self, wait: bool = True, cancel_futures: bool = False):
        pass


def _dump(value: Any) -> Any:
    return value.model_dump() if isinstance(value, pydantic.BaseModel) else value
