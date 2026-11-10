"""
Flow: run steps as a DAG, passing each step's output to the steps it depends on.

A flow is a set of FlowStepSpecs (the nodes) and FlowEdges (the order). Each
spec names a processor (a registered name like "echo", or
"package.module:ClassName") that handles the step, a unique id and a config. Edges are added with
Flow.add_edge() or inferred from a step's ``depends_on`` list. Steps are never
wired automatically: a step without edges is an independent root.

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
import os
import re
import threading
import time
import tomllib
import uuid
from collections.abc import Callable, Generator
from concurrent.futures import FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar, Literal

import pydantic
import tomli_w
import yaml

logger = logging.getLogger(__name__)

RESERVED_IDS = {"input", "vars"}
YAML_SUFFIXES = (".yaml", ".yml")


class FlowError(Exception):
    pass


class FlowAborted(Exception):
    """Raised by FlowContext.abort() to stop the flow."""


class FlowStepSpec(pydantic.BaseModel):
    id: str
    processor: str
    config: dict[str, Any] = {}
    on_error: Literal["stop", "continue"] = "stop"
    # ids of steps this step runs after; each one adds an edge (dependency_id -> id)
    depends_on: list[str] = []

    @pydantic.field_validator("depends_on", mode="before")
    @classmethod
    def _depends_on_as_list(cls, v: Any) -> Any:
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
    context_id: str | None = None  # FlowContext.id of the run
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


class FlowSnapshot(pydantic.BaseModel):
    """
    State of a flow run: the flow definition, the input and the results so far.
    Written by Flow.run(snapshot=...) while the flow runs and when it ends.
    """

    context_id: str  # FlowContext.id of the run
    flow: dict  # Flow.to_dict()
    input: Any = None
    status: Literal["running", "success", "failed", "aborted"]
    started_at: datetime
    updated_at: datetime
    steps: list[
        StepResult
    ] = []  # finished (and, at the end, skipped) steps, in execution order
    running: list[str] = []
    pending: list[str] = []

    def get(self, step_id: str) -> StepResult | None:
        return next((r for r in self.steps if r.step_id == step_id), None)

    def to_flow(self) -> "Flow":
        return Flow.from_dict(self.flow)

    def to_json(self, indent: int | None = 2) -> str:
        # the input is stored as is and may not be JSON serializable: fall back to str() for it
        data = self.model_dump(mode="json", exclude={"input"})
        data = {
            "context_id": data.pop("context_id"),
            "flow": data.pop("flow"),
            "input": self.input,
            **data,
        }
        return json.dumps(data, indent=indent, default=str)

    def save(self, path: str | Path):
        """Write the snapshot as JSON. The file is replaced atomically, so readers never see a partial file."""
        path = Path(path)
        tmp = path.with_name(f".{path.name}.tmp")
        tmp.write_text(self.to_json() + "\n")
        os.replace(tmp, path)

    @classmethod
    def load(cls, path: str | Path) -> "FlowSnapshot":
        return cls.model_validate_json(Path(path).read_text())


class FlowContext:
    """
    Run state shared by all steps of one flow run.

    With parallel execution, steps call into the context from worker threads:
    results are only written by the runner thread, and events are delivered
    to on_event one at a time.
    """

    def __init__(
        self,
        flow_name: str,
        input_data: Any = None,
        variables: dict | None = None,
        on_event: Callable[[StepEvent], None] | None = None,
        context_id: str | None = None,
    ):
        # unique id of the run; generated unless given
        self.id = context_id or uuid.uuid4().hex
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


def _config_references(value: Any) -> set[str]:
    """The ${...} references (without the braces) in strings inside value; $${...} escapes are skipped"""
    if isinstance(value, str):
        return {
            m.group(1) for m in _REF.finditer(value) if not m.group(0).startswith("$$")
        }
    if isinstance(value, dict):
        return set().union(*(_config_references(v) for v in value.values()))
    if isinstance(value, (list, tuple)):
        return set().union(*(_config_references(v) for v in value))
    return set()


def _get_item(value: Any, key: str, ref: str) -> Any:
    try:
        if isinstance(value, dict):
            return value[key]
        if isinstance(value, (list, tuple)):
            return value[int(key)]
        return getattr(value, key)
    except KeyError, IndexError, ValueError, AttributeError:
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
        self.config = (
            self.config_model.model_validate(config) if self.config_model else config
        )

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
            raise FlowError(
                f"Processor class '{class_name}' not found in '{module_name}'"
            )
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

    def __init__(
        self,
        name: str,
        steps: list[FlowStepSpec | dict] | None = None,
        edges: list[FlowEdge | dict | tuple[str, str]] | None = None,
        variables: dict | None = None,
        max_workers: int = 1,
    ):
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

    def add_edge(
        self, edge: FlowEdge | dict | tuple[str, str] | str, to_step: str | None = None
    ) -> FlowEdge:
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
        All edges: explicit ones plus those inferred from each step's `depends_on`.
        A step without edges is an independent root.
        """
        edges = list(self._edges)
        for step in self.steps:
            for dep in step.depends_on:
                edge = FlowEdge(from_step=dep, to_step=step.id)
                if edge not in edges:
                    edges.append(edge)
        return edges

    def predecessors(self) -> dict[str, list[str]]:
        """Map of step id -> ids of the steps it runs after (in edge order)"""
        ids = {s.id for s in self.steps}
        preds: dict[str, list[str]] = {s.id: [] for s in self.steps}
        for e in self.edges:
            for step_id in (e.from_step, e.to_step):
                if step_id not in ids:
                    raise FlowError(
                        f"Edge {e.from_step} -> {e.to_step}: unknown step '{step_id}'"
                    )
            preds[e.to_step].append(e.from_step)
        return preds

    def ancestors(self) -> dict[str, set[str]]:
        """Map of step id -> ids of all steps it runs after, directly or indirectly"""
        preds = self.predecessors()
        result: dict[str, set[str]] = {}
        for step_id in preds:
            seen: set[str] = set()
            todo = list(preds[step_id])
            while todo:
                p = todo.pop()
                if p not in seen:
                    seen.add(p)
                    todo.extend(preds[p])
            result[step_id] = seen
        return result

    def check_references(self) -> list[str]:
        """
        Warnings for ${...} references in step configs that may not resolve: a reference
        to a step the referencing step doesn't depend on (directly or indirectly), to
        the step itself, or to an unknown name. Raises FlowError if an edge references an unknown step.
        """
        ancestors = self.ancestors()
        warnings = []
        for step in self.steps:
            for ref in sorted(_config_references(step.config)):
                head = ref.strip().split(".")[0]
                if head in RESERVED_IDS or head in ancestors[step.id]:
                    continue
                if head == step.id:
                    problem = "references itself"
                elif head in ancestors:
                    problem = f"doesn't depend on '{head}'; add it to depends_on"
                else:
                    problem = f"unknown step '{head}'"
                warnings.append(f"Step '{step.id}': reference '${{{ref}}}': {problem}")
        return warnings

    def execution_order(self) -> list[FlowStepSpec]:
        """Topological order of the steps; ties keep insertion order. Raises FlowError on cycles."""
        preds = self.predecessors()
        done: set[str] = set()
        order: list[FlowStepSpec] = []
        remaining = list(self.steps)
        while remaining:
            ready = next(
                (s for s in remaining if all(p in done for p in preds[s.id])), None
            )
            if ready is None:
                raise FlowError(
                    f"Cycle between steps: {', '.join(s.id for s in remaining)}"
                )
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
            lines.append(
                f'    {node[s.id]}["{label(s.id)}<br/>({label(s.processor)})"]'
            )
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
            lines.append(
                f'    {quote(s.id)} [label="{esc(s.id)}\\n{esc(s.processor)}"];'
            )
        for e in self.edges:
            lines.append(f"    {quote(e.from_step)} -> {quote(e.to_step)};")
        lines.append("}")
        return "\n".join(lines) + "\n"

    @classmethod
    def from_dict(cls, data: dict) -> "Flow":
        return cls(
            name=data["name"],
            steps=data.get("steps", []),
            edges=data.get("edges"),
            variables=data.get("vars"),
            max_workers=data.get("max_workers", 1),
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "Flow":
        """Load a flow from a .yaml/.yml, .json or .toml file"""
        path = Path(path)
        if path.suffix == ".toml":
            data = tomllib.loads(path.read_text())
        elif path.suffix == ".json":
            data = json.loads(path.read_text())
        elif path.suffix in YAML_SUFFIXES:
            try:
                data = yaml.safe_load(path.read_text())
            except yaml.YAMLError as e:
                raise FlowError(f"Invalid YAML: {e}") from None
        else:
            raise FlowError(f"Unsupported flow file type '{path.suffix}'")
        return cls.from_dict(data)

    def to_dict(self) -> dict:
        """
        The flow definition in the structure from_dict() reads. Step fields with
        default values are left out; edges are the explicit ones (not those from `depends_on`).
        """
        data: dict[str, Any] = {"name": self.name, "max_workers": self.max_workers}
        if self.variables:
            data["vars"] = self.variables
        if self._edges:
            data["edges"] = [e.model_dump() for e in self._edges]
        data["steps"] = [s.model_dump(exclude_defaults=True) for s in self.steps]
        return data

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    def to_file(self, path: str | Path):
        """Write the flow definition to a .yaml/.yml, .json or .toml file, readable with from_file()"""
        path = Path(path)
        if path.suffix == ".toml":
            text = tomli_w.dumps(self.to_dict())
        elif path.suffix == ".json":
            text = self.to_json() + "\n"
        elif path.suffix in YAML_SUFFIXES:
            text = yaml.safe_dump(self.to_dict(), sort_keys=False, allow_unicode=True)
        else:
            raise FlowError(f"Unsupported flow file type '{path.suffix}'")
        path.write_text(text)

    def run(
        self,
        input_data: Any = None,
        on_event: Callable[[StepEvent], None] | None = None,
        max_workers: int | None = None,
        snapshot: str | Path | Callable[[FlowSnapshot], None] | None = None,
        context_id: str | None = None,
    ) -> FlowResult:
        """
        Run the flow. max_workers overrides Flow.max_workers for this run.
        context_id identifies the run (FlowContext.id); a random id is generated if not given.
        snapshot is a file path or a callback that gets a FlowSnapshot when the run starts,
        after steps finish and when the run ends (from the runner thread). Errors while
        saving a snapshot are logged and don't stop the flow.
        Raises FlowError for an invalid graph (unknown step in an edge, cycle) or max_workers < 1.
        """
        workers = self.max_workers if max_workers is None else max_workers
        if workers < 1:
            raise FlowError(f"max_workers must be at least 1, got {workers}")
        order = self.execution_order()
        preds = self.predecessors()
        for warning in self.check_references():
            logger.warning("Flow '%s': %s", self.name, warning)
        ctx = FlowContext(
            self.name,
            input_data=input_data,
            variables=self.variables,
            on_event=on_event,
            context_id=context_id,
        )
        results: dict[str, StepResult] = {}
        # outputs of finished steps; a failed step with on_error="continue" contributes None
        outputs: dict[str, Any] = {}
        pending = list(order)
        running: dict[Future, FlowStepSpec] = {}
        status = "success"
        flow_dict = self.to_dict() if snapshot is not None else None
        started_at = datetime.now(UTC)

        def save_snapshot(snapshot_status: str):
            if snapshot is None:
                return
            snap = FlowSnapshot(
                context_id=ctx.id,
                flow=flow_dict,
                input=input_data,
                status=snapshot_status,
                started_at=started_at,
                updated_at=datetime.now(UTC),
                steps=[results[s.id] for s in order if s.id in results],
                running=[s.id for s in running.values()],
                pending=[s.id for s in pending],
            )
            try:
                snapshot(snap) if callable(snapshot) else snap.save(snapshot)
            except Exception as e:
                logger.warning("Cannot save snapshot of flow '%s': %s", self.name, e)

        save_snapshot("running")
        executor = (
            ThreadPoolExecutor(
                max_workers=workers, thread_name_prefix=f"flow-{self.name}"
            )
            if workers > 1
            else _InlineExecutor()
        )
        try:
            while True:
                # start every ready step (all predecessors finished), in execution order
                if not ctx.stopping:
                    for spec in list(pending):
                        if len(running) >= workers:
                            break
                        if all(p in results for p in preds[spec.id]):
                            pending.remove(spec)
                            step_input = _step_input(
                                preds[spec.id], outputs, input_data
                            )
                            running[
                                executor.submit(
                                    self._execute_step, spec, step_input, ctx
                                )
                            ] = spec
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
                save_snapshot("running")
        finally:
            ctx._stopping.set()
            executor.shutdown(wait=True, cancel_futures=True)

        for spec in list(pending):
            results[spec.id] = StepResult(step_id=spec.id, status="skipped")
            pending.remove(spec)
        save_snapshot(status)
        return FlowResult(
            name=self.name,
            context_id=ctx.id,
            status=status,
            steps=[results[s.id] for s in order],
        )

    def _execute_step(
        self, spec: FlowStepSpec, input_data: Any, ctx: FlowContext
    ) -> StepResult:
        ctx.emit("step.start", {"processor": spec.processor}, step_id=spec.id)
        started = time.monotonic()
        try:
            step = get_step_processor_class(spec.processor)(
                config=ctx.resolve(spec.config)
            )
            output = self._drive(step, spec, input_data, ctx)
            output = _dump(
                step.output_model.model_validate(output)
                if step.output_model
                else output
            )
            result = StepResult(step_id=spec.id, status="success", output=output)
        except FlowAborted as e:
            result = StepResult(step_id=spec.id, status="aborted", error=str(e))
        except Exception as e:
            logger.warning("Step '%s' failed: %s", spec.id, e)
            result = StepResult(
                step_id=spec.id, status="failed", error=f"{type(e).__name__}: {e}"
            )
        result.duration = time.monotonic() - started
        ctx.emit(
            "step.end",
            {"status": result.status, "error": result.error},
            step_id=spec.id,
        )
        return result

    @staticmethod
    def _drive(
        step: FlowProcessor, spec: FlowStepSpec, input_data: Any, ctx: FlowContext
    ) -> Any:
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
