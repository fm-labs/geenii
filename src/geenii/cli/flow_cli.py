import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import click

from geenii.flow import (
    Flow,
    FlowError,
    StepEvent,
    get_step_processor_class,
    list_processor_types,
)


def _parse_value(value: str):
    """Parse a value as JSON, falling back to the plain string"""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _import_processor_modules(modules: tuple[str, ...]):
    for module in modules:
        try:
            importlib.import_module(module)
        except ImportError as e:
            raise click.ClickException(
                f"Cannot import processor module '{module}': {e}"
            )


def _load_flow(path: str, modules: tuple[str, ...]) -> Flow:
    _import_processor_modules(modules)
    try:
        return Flow.from_file(path)
    except (FlowError, ValueError, KeyError) as e:
        # ValueError covers JSON/TOML syntax and pydantic validation errors
        raise click.ClickException(f"Invalid flow file '{path}': {e}")


def _check_flow(flow: Flow) -> list[str]:
    """Return a list of problems: invalid graph and unknown processor types"""
    problems = []
    try:
        flow.execution_order()
    except FlowError as e:
        problems.append(str(e))
    for step in flow.steps:
        try:
            get_step_processor_class(step.processor)
        except (FlowError, ImportError) as e:
            problems.append(f"Step '{step.id}': {e}")
    return problems


def _print_event(event: StepEvent):
    if event.type == "step.start":
        click.echo(f"[{event.step_id}] start ({event.data['processor']})", err=True)
    elif event.type == "step.end":
        error = f": {event.data['error']}" if event.data["error"] else ""
        click.echo(f"[{event.step_id}] {event.data['status']}{error}", err=True)
    else:
        click.echo(f"[{event.step_id}] {event.type}: {event.data}", err=True)


processor_module_option = click.option(
    "--processor-module",
    "-m",
    "processor_modules",
    multiple=True,
    metavar="MODULE",
    help="Import a Python module that registers custom processors (repeatable).",
)


@click.group()
def flow():
    """Run and inspect flows (step pipelines)."""


@flow.command()
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--input",
    "-i",
    "input_value",
    default=None,
    help="Flow input: JSON, a plain string, or '-' to read it from stdin.",
)
@click.option(
    "--var",
    "-v",
    "variables",
    multiple=True,
    metavar="KEY=VALUE",
    help="Set a flow variable (repeatable). VALUE is parsed as JSON if possible.",
)
@click.option(
    "--max-workers",
    "-w",
    type=int,
    default=None,
    help="Number of steps that may run at the same time (overrides the flow file).",
)
@click.option(
    "--json",
    "as_json",
    is_flag=True,
    default=False,
    help="Print the full result as JSON.",
)
@click.option(
    "--quiet", "-q", is_flag=True, default=False, help="Don't print step events."
)
@click.option(
    "--snapshot",
    "-s",
    "snapshot_path",
    type=click.Path(dir_okay=False),
    default=None,
    help="Write the flow, its input and the step results to this JSON file while the flow runs and when it ends.",
)
@click.option(
    "--context-id", default=None, help="Id of the run (default: a generated id)."
)
@processor_module_option
def run(
    path,
    input_value,
    variables,
    max_workers,
    as_json,
    quiet,
    snapshot_path,
    context_id,
    processor_modules,
):
    """Run the flow in PATH (.yaml/.yml, .json or .toml).

    Step events are printed to stderr. Exits with code 1 if the flow failed or was aborted.
    """
    f = _load_flow(path, processor_modules)

    for item in variables:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise click.BadParameter(
                f"Expected KEY=VALUE, got '{item}'", param_hint="--var"
            )
        f.variables[key] = _parse_value(value)

    input_data = None
    if input_value == "-":
        input_data = _parse_value(sys.stdin.read())
    elif input_value is not None:
        input_data = _parse_value(input_value)

    try:
        result = f.run(
            input_data=input_data,
            max_workers=max_workers,
            on_event=None if quiet else _print_event,
            snapshot=snapshot_path,
            context_id=context_id,
        )
    except FlowError as e:
        raise click.ClickException(str(e))

    if as_json:
        click.echo(result.model_dump_json(indent=2))
    else:
        click.echo(f"\nFlow '{result.name}' ({result.context_id}): {result.status}")
        for step in result.steps:
            error = f"  {step.error}" if step.error else ""
            click.echo(
                f"  {step.step_id:20} {step.status:8} {step.duration:7.3f}s{error}"
            )
        click.echo("\nOutput:")
        click.echo(json.dumps(result.output, indent=2, default=str))

    if result.status != "success":
        raise SystemExit(1)


@flow.command()
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@click.option("--strict", is_flag=True, default=False, help="Treat warnings as errors.")
@processor_module_option
def validate(path, strict, processor_modules):
    """Check the flow in PATH and print its execution order.

    Checks the file, the graph (unknown steps in edges, cycles) and the processor types.
    Warns about ${...} references to steps that a step doesn't depend on.
    Exits with code 1 if there are problems (or warnings, with --strict).
    """
    f = _load_flow(path, processor_modules)
    problems = _check_flow(f)
    if problems:
        for problem in problems:
            click.echo(f"error: {problem}", err=True)
        raise SystemExit(1)

    warnings = f.check_references()
    for warning in warnings:
        click.echo(f"warning: {warning}", err=True)
    if warnings and strict:
        raise SystemExit(1)

    preds = f.predecessors()
    click.echo(
        f"Flow '{f.name}' is valid ({len(f.steps)} steps, max_workers={f.max_workers})"
    )
    click.echo("\nExecution order:")
    for step in f.execution_order():
        after = f"  (after {', '.join(preds[step.id])})" if preds[step.id] else ""
        click.echo(f"  {step.id} [{step.processor}]{after}")


GRAPH_IMAGE_FORMATS = ("svg", "png", "pdf")
GRAPH_SUFFIX_FORMATS = {
    ".mmd": "mermaid",
    ".mermaid": "mermaid",
    ".md": "mermaid",
    ".dot": "dot",
    ".gv": "dot",
    **{f".{f}": f for f in GRAPH_IMAGE_FORMATS},
}


@flow.command()
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "--format",
    "-f",
    "fmt",
    type=click.Choice(["mermaid", "dot", *GRAPH_IMAGE_FORMATS]),
    default=None,
    help="Output format. Default: from the --output file extension, else mermaid.",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(dir_okay=False),
    default=None,
    help="Write to this file instead of stdout. Required for image formats.",
)
@click.option(
    "--direction",
    "-d",
    type=click.Choice(["LR", "TB", "RL", "BT"]),
    default="LR",
    help="Layout direction (default LR: left to right).",
)
@processor_module_option
def graph(path, fmt, output, direction, processor_modules):
    """Print the graph of the flow in PATH as Mermaid or Graphviz DOT, or render it to an image.

    Image formats (svg, png, pdf) are rendered with Graphviz, so the `dot` command must be installed.
    """
    f = _load_flow(path, processor_modules)
    if fmt is None:
        fmt = (
            GRAPH_SUFFIX_FORMATS.get(Path(output).suffix.lower(), "mermaid")
            if output
            else "mermaid"
        )

    try:
        text = f.to_mermaid(direction) if fmt == "mermaid" else f.to_dot(direction)
    except FlowError as e:
        raise click.ClickException(str(e))

    if fmt in GRAPH_IMAGE_FORMATS:
        if not output:
            raise click.UsageError(f"--output is required for format '{fmt}'")
        dot = shutil.which("dot")
        if not dot:
            raise click.ClickException(
                "Graphviz 'dot' not found; install Graphviz (e.g. `brew install graphviz`) "
                "or use --format dot / mermaid"
            )
        proc = subprocess.run(
            [dot, f"-T{fmt}", "-o", output],
            input=text,
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode != 0:
            raise click.ClickException(f"dot failed: {proc.stderr.strip()}")
        click.echo(f"Wrote {output}", err=True)
    elif output:
        Path(output).write_text(text)
        click.echo(f"Wrote {output}", err=True)
    else:
        click.echo(text, nl=False)


@flow.command(name="list")
@click.option(
    "--json", "as_json", is_flag=True, default=False, help="Print the flows as JSON."
)
def list_flows(as_json):
    """List the flows in ~/.geenii/flows and the working directory's .geenii/flows."""
    from geenii.config import flow_dirs
    from geenii.g import init_flow_registry

    flows = init_flow_registry().flows
    if as_json:
        click.echo(
            json.dumps(
                [{"name": f.name, "filepath": f.filepath} for f in flows], indent=2
            )
        )
        return
    if not flows:
        click.echo("No flows found in:")
        for d in flow_dirs():
            click.echo(f"  {d}")
        return
    width = max(len(f.name) for f in flows)
    for f in flows:
        click.echo(f"  {f.name:{width}}  {f.filepath}")


@flow.command()
@processor_module_option
def processors(processor_modules):
    """List the registered processor types."""
    _import_processor_modules(processor_modules)
    for name, cls in list_processor_types().items():
        doc = (cls.__doc__ or "").strip().splitlines()
        click.echo(f"{name:20} {doc[0] if doc else ''}")
