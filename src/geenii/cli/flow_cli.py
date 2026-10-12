import importlib
import json
import sys

import click

from geenii.flow import Flow, FlowError, StepEvent, get_step_class, list_step_types


def _parse_value(value: str):
    """Parse a value as JSON, falling back to the plain string"""
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _import_step_modules(modules: tuple[str, ...]):
    for module in modules:
        try:
            importlib.import_module(module)
        except ImportError as e:
            raise click.ClickException(f"Cannot import step module '{module}': {e}")


def _load_flow(path: str, modules: tuple[str, ...]) -> Flow:
    _import_step_modules(modules)
    try:
        return Flow.from_file(path)
    except (FlowError, ValueError, KeyError) as e:
        # ValueError covers JSON/TOML syntax and pydantic validation errors
        raise click.ClickException(f"Invalid flow file '{path}': {e}")


def _check_flow(flow: Flow) -> list[str]:
    """Return a list of problems: invalid graph and unknown step types"""
    problems = []
    try:
        flow.execution_order()
    except FlowError as e:
        problems.append(str(e))
    for step in flow.steps:
        try:
            get_step_class(step.type)
        except (FlowError, ImportError) as e:
            problems.append(f"Step '{step.id}': {e}")
    return problems


def _print_event(event: StepEvent):
    if event.type == "step.start":
        click.echo(f"[{event.step_id}] start ({event.data['type']})", err=True)
    elif event.type == "step.end":
        error = f": {event.data['error']}" if event.data["error"] else ""
        click.echo(f"[{event.step_id}] {event.data['status']}{error}", err=True)
    else:
        click.echo(f"[{event.step_id}] {event.type}: {event.data}", err=True)


step_module_option = click.option(
    "--step-module", "-m", "step_modules", multiple=True, metavar="MODULE",
    help="Import a Python module that registers custom steps (repeatable).")


@click.group()
def flow():
    """Run and inspect flows (step pipelines)."""
    pass


@flow.command()
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@click.option("--input", "-i", "input_value", default=None,
              help="Flow input: JSON, a plain string, or '-' to read it from stdin.")
@click.option("--var", "-v", "variables", multiple=True, metavar="KEY=VALUE",
              help="Set a flow variable (repeatable). VALUE is parsed as JSON if possible.")
@click.option("--max-workers", "-w", type=int, default=None,
              help="Number of steps that may run at the same time (overrides the flow file).")
@click.option("--json", "as_json", is_flag=True, default=False,
              help="Print the full result as JSON.")
@click.option("--quiet", "-q", is_flag=True, default=False, help="Don't print step events.")
@step_module_option
def run(path, input_value, variables, max_workers, as_json, quiet, step_modules):
    """Run the flow in PATH (.toml or .json).

    Step events are printed to stderr. Exits with code 1 if the flow failed or was aborted.
    """
    f = _load_flow(path, step_modules)

    for item in variables:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise click.BadParameter(f"Expected KEY=VALUE, got '{item}'", param_hint="--var")
        f.variables[key] = _parse_value(value)

    input_data = None
    if input_value == "-":
        input_data = _parse_value(sys.stdin.read())
    elif input_value is not None:
        input_data = _parse_value(input_value)

    try:
        result = f.run(input_data=input_data, max_workers=max_workers,
                       on_event=None if quiet else _print_event)
    except FlowError as e:
        raise click.ClickException(str(e))

    if as_json:
        click.echo(result.model_dump_json(indent=2))
    else:
        click.echo(f"\nFlow '{result.name}': {result.status}")
        for step in result.steps:
            error = f"  {step.error}" if step.error else ""
            click.echo(f"  {step.step_id:20} {step.status:8} {step.duration:7.3f}s{error}")
        click.echo("\nOutput:")
        click.echo(json.dumps(result.output, indent=2, default=str))

    if result.status != "success":
        raise SystemExit(1)


@flow.command()
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
@step_module_option
def validate(path, step_modules):
    """Check the flow in PATH and print its execution order.

    Checks the file, the graph (unknown steps in edges, cycles) and the step types.
    Exits with code 1 if there are problems.
    """
    f = _load_flow(path, step_modules)
    problems = _check_flow(f)
    if problems:
        for problem in problems:
            click.echo(f"error: {problem}", err=True)
        raise SystemExit(1)

    preds = f.predecessors()
    click.echo(f"Flow '{f.name}' is valid ({len(f.steps)} steps, max_workers={f.max_workers})")
    click.echo("\nExecution order:")
    for step in f.execution_order():
        after = f"  (after {', '.join(preds[step.id])})" if preds[step.id] else ""
        click.echo(f"  {step.id} [{step.type}]{after}")


@flow.command()
@step_module_option
def steps(step_modules):
    """List the registered step types."""
    _import_step_modules(step_modules)
    for name, cls in list_step_types().items():
        doc = (cls.__doc__ or "").strip().splitlines()
        click.echo(f"{name:20} {doc[0] if doc else ''}")
