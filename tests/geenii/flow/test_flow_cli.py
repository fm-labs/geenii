import json
import shutil

import pytest
from click.testing import CliRunner

from geenii.cli.flow_cli import flow


@pytest.fixture
def runner():
    return CliRunner()


def _write(tmp_path, data: dict, name: str = "flow.json"):
    path = tmp_path / name
    path.write_text(json.dumps(data))
    return str(path)


def test_run_success_with_input_and_vars(runner, tmp_path):
    path = _write(tmp_path, {"name": "f", "steps": [
        {"id": "a", "type": "echo", "config": {"message": "${input.n} ${vars.who}"}},
    ]})
    result = runner.invoke(flow, ["run", path, "-q", "--json", "-i", '{"n": 1}', "-v", "who=me"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["status"] == "success"
    assert data["steps"][0]["output"] == {"message": "1 me"}


def test_run_input_from_stdin_and_events(runner, tmp_path):
    path = _write(tmp_path, {"name": "f", "steps": [{"id": "a", "type": "echo"}]})
    result = runner.invoke(flow, ["run", path], input="plain text\n")
    assert result.exit_code == 0
    assert "[a] start (echo)" in result.stderr
    assert "Flow 'f': success" in result.stdout

    result = runner.invoke(flow, ["run", path, "-q", "--json", "-i", "-"], input="plain text\n")
    assert json.loads(result.stdout)["steps"][0]["output"] == {"message": "plain text\n"}


def test_run_failed_flow_exits_1(runner, tmp_path):
    path = _write(tmp_path, {"name": "f", "steps": [
        {"id": "a", "type": "execute_command", "config": {"command": "false", "check": True}},
    ]})
    result = runner.invoke(flow, ["run", path, "-q"])
    assert result.exit_code == 1
    assert "failed" in result.stdout


def test_run_invalid_graph_and_file(runner, tmp_path):
    path = _write(tmp_path, {"name": "f", "steps": [{"id": "a", "type": "echo", "after": "x"}]})
    result = runner.invoke(flow, ["run", path])
    assert result.exit_code == 1
    assert "unknown step 'x'" in result.stderr

    bad = tmp_path / "bad.toml"
    bad.write_text("name = ")
    result = runner.invoke(flow, ["run", str(bad)])
    assert result.exit_code == 1
    assert "Invalid flow file" in result.stderr

    result = runner.invoke(flow, ["run", path, "-v", "novalue"])
    assert result.exit_code == 2


def test_validate(runner, tmp_path):
    path = _write(tmp_path, {"name": "f", "steps": [
        {"id": "b", "type": "echo", "after": "a"},
        {"id": "a", "type": "echo"},
    ]})
    result = runner.invoke(flow, ["validate", path])
    assert result.exit_code == 0
    assert result.stdout.index("  a [echo]") < result.stdout.index("  b [echo]  (after a)")

    path = _write(tmp_path, {"name": "f", "steps": [
        {"id": "a", "type": "nope", "after": "b"},
        {"id": "b", "type": "echo", "after": "a"},
    ]}, name="bad.json")
    result = runner.invoke(flow, ["validate", path])
    assert result.exit_code == 1
    assert "Cycle" in result.stderr
    assert "Unknown step type 'nope'" in result.stderr


def test_steps_with_custom_module(runner, tmp_path, monkeypatch):
    (tmp_path / "my_cli_steps.py").write_text(
        "from geenii.flow import FlowStep, register_step\n\n"
        "@register_step('my_cli_step')\n"
        "class MyStep(FlowStep):\n"
        "    \"\"\"Does custom things\"\"\"\n"
        "    def process(self, input_data, ctx):\n"
        "        return {'ok': True}\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    result = runner.invoke(flow, ["steps", "-m", "my_cli_steps"])
    assert result.exit_code == 0
    assert "echo" in result.stdout
    assert "my_cli_step" in result.stdout and "Does custom things" in result.stdout

    result = runner.invoke(flow, ["steps", "-m", "does_not_exist_xyz"])
    assert result.exit_code == 1


def _graph_file(tmp_path):
    return _write(tmp_path, {"name": "f", "steps": [
        {"id": "a", "type": "echo"},
        {"id": "b", "type": "echo", "after": "a"},
    ]})


def test_graph_mermaid_to_stdout(runner, tmp_path):
    result = runner.invoke(flow, ["graph", _graph_file(tmp_path)])
    assert result.exit_code == 0
    assert result.stdout.startswith("flowchart LR\n")
    assert "n0 --> n1" in result.stdout


def test_graph_format_from_output_suffix(runner, tmp_path):
    out = tmp_path / "g.dot"
    result = runner.invoke(flow, ["graph", _graph_file(tmp_path), "-o", str(out), "-d", "TB"])
    assert result.exit_code == 0
    assert out.read_text().startswith('digraph "f" {\n    rankdir=TB;')

    out = tmp_path / "g.mmd"
    runner.invoke(flow, ["graph", _graph_file(tmp_path), "-o", str(out)])
    assert out.read_text().startswith("flowchart")


def test_graph_image_needs_output_and_dot(runner, tmp_path, monkeypatch):
    result = runner.invoke(flow, ["graph", _graph_file(tmp_path), "-f", "svg"])
    assert result.exit_code == 2
    assert "--output is required" in result.stderr

    monkeypatch.setattr("geenii.cli.flow_cli.shutil.which", lambda name: None)
    result = runner.invoke(flow, ["graph", _graph_file(tmp_path), "-o", str(tmp_path / "g.svg")])
    assert result.exit_code == 1
    assert "Graphviz 'dot' not found" in result.stderr


@pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz not installed")
def test_graph_renders_svg(runner, tmp_path):
    out = tmp_path / "g.svg"
    result = runner.invoke(flow, ["graph", _graph_file(tmp_path), "-o", str(out)])
    assert result.exit_code == 0, result.stderr
    assert "<svg" in out.read_text()
