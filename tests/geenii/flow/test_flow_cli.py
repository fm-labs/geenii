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
    path = _write(
        tmp_path,
        {
            "name": "f",
            "steps": [
                {
                    "id": "a",
                    "processor": "echo",
                    "config": {"message": "${input.n} ${vars.who}"},
                },
            ],
        },
    )
    result = runner.invoke(
        flow, ["run", path, "-q", "--json", "-i", '{"n": 1}', "-v", "who=me"]
    )
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["status"] == "success"
    assert data["steps"][0]["output"] == {"message": "1 me"}


def test_run_input_from_stdin_and_events(runner, tmp_path):
    path = _write(tmp_path, {"name": "f", "steps": [{"id": "a", "processor": "echo"}]})
    result = runner.invoke(flow, ["run", path], input="plain text\n")
    assert result.exit_code == 0
    assert "[a] start (echo)" in result.stderr
    assert "Flow 'f' (" in result.stdout and "): success" in result.stdout

    result = runner.invoke(
        flow, ["run", path, "-q", "--json", "-i", "-"], input="plain text\n"
    )
    assert json.loads(result.stdout)["steps"][0]["output"] == {
        "message": "plain text\n"
    }


def test_run_failed_flow_exits_1(runner, tmp_path):
    path = _write(
        tmp_path,
        {
            "name": "f",
            "steps": [
                {
                    "id": "a",
                    "processor": "execute_command",
                    "config": {"command": "false", "check": True},
                },
            ],
        },
    )
    result = runner.invoke(flow, ["run", path, "-q"])
    assert result.exit_code == 1
    assert "failed" in result.stdout


def test_run_snapshot(runner, tmp_path):
    path = _write(
        tmp_path,
        {
            "name": "f",
            "steps": [
                {"id": "a", "processor": "echo", "config": {"message": "hi"}},
                {
                    "id": "b",
                    "processor": "execute_command",
                    "config": {"command": "false", "check": True},
                },
                {"id": "c", "processor": "echo"},
            ],
        },
    )
    snapshot = tmp_path / "snap.json"
    result = runner.invoke(
        flow,
        [
            "run",
            path,
            "-q",
            "-i",
            "x",
            "--snapshot",
            str(snapshot),
            "--context-id",
            "run-1",
        ],
    )
    assert result.exit_code == 1
    assert "Flow 'f' (run-1): failed" in result.stdout
    data = json.loads(snapshot.read_text())
    assert data["context_id"] == "run-1"
    assert data["status"] == "failed"
    assert data["input"] == "x"
    assert data["flow"]["name"] == "f"
    assert [(s["step_id"], s["status"]) for s in data["steps"]] == [
        ("a", "success"),
        ("b", "failed"),
        ("c", "skipped"),
    ]
    assert data["steps"][0]["output"] == {"message": "hi"}


def test_run_invalid_graph_and_file(runner, tmp_path):
    path = _write(
        tmp_path,
        {"name": "f", "steps": [{"id": "a", "processor": "echo", "depends_on": "x"}]},
    )
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
    path = _write(
        tmp_path,
        {
            "name": "f",
            "steps": [
                {"id": "b", "processor": "echo", "depends_on": "a"},
                {"id": "a", "processor": "echo"},
            ],
        },
    )
    result = runner.invoke(flow, ["validate", path])
    assert result.exit_code == 0
    assert result.stdout.index("  a [echo]") < result.stdout.index(
        "  b [echo]  (after a)"
    )

    path = _write(
        tmp_path,
        {
            "name": "f",
            "steps": [
                {"id": "a", "processor": "nope", "depends_on": "b"},
                {"id": "b", "processor": "echo", "depends_on": "a"},
            ],
        },
        name="bad.json",
    )
    result = runner.invoke(flow, ["validate", path])
    assert result.exit_code == 1
    assert "Cycle" in result.stderr
    assert "Unknown processor type 'nope'" in result.stderr


def test_validate_reference_warnings(runner, tmp_path):
    path = _write(
        tmp_path,
        {
            "name": "f",
            "steps": [
                {"id": "a", "processor": "echo"},
                {"id": "b", "processor": "echo", "config": {"message": "${a.message}"}},
            ],
        },
    )
    result = runner.invoke(flow, ["validate", path])
    assert result.exit_code == 0
    assert (
        "warning: Step 'b': reference '${a.message}': doesn't depend on 'a'"
        in result.stderr
    )
    assert "is valid" in result.stdout

    result = runner.invoke(flow, ["validate", path, "--strict"])
    assert result.exit_code == 1
    assert "warning: Step 'b'" in result.stderr


def test_processors_with_custom_module(runner, tmp_path, monkeypatch):
    (tmp_path / "my_cli_processors.py").write_text(
        "from geenii.flow import FlowProcessor, register_processor\n\n"
        "@register_processor('my_cli_step')\n"
        "class MyProcessor(FlowProcessor):\n"
        '    """Does custom things"""\n'
        "    def process(self, input_data, ctx):\n"
        "        return {'ok': True}\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    result = runner.invoke(flow, ["processors", "-m", "my_cli_processors"])
    assert result.exit_code == 0
    assert "echo" in result.stdout
    assert "my_cli_step" in result.stdout and "Does custom things" in result.stdout

    result = runner.invoke(flow, ["processors", "-m", "does_not_exist_xyz"])
    assert result.exit_code == 1


def _graph_file(tmp_path):
    return _write(
        tmp_path,
        {
            "name": "f",
            "steps": [
                {"id": "a", "processor": "echo"},
                {"id": "b", "processor": "echo", "depends_on": "a"},
            ],
        },
    )


def test_graph_mermaid_to_stdout(runner, tmp_path):
    result = runner.invoke(flow, ["graph", _graph_file(tmp_path)])
    assert result.exit_code == 0
    assert result.stdout.startswith("flowchart LR\n")
    assert "n0 --> n1" in result.stdout


def test_graph_format_from_output_suffix(runner, tmp_path):
    out = tmp_path / "g.dot"
    result = runner.invoke(
        flow, ["graph", _graph_file(tmp_path), "-o", str(out), "-d", "TB"]
    )
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
    result = runner.invoke(
        flow, ["graph", _graph_file(tmp_path), "-o", str(tmp_path / "g.svg")]
    )
    assert result.exit_code == 1
    assert "Graphviz 'dot' not found" in result.stderr


@pytest.mark.skipif(shutil.which("dot") is None, reason="Graphviz not installed")
def test_graph_renders_svg(runner, tmp_path):
    out = tmp_path / "g.svg"
    result = runner.invoke(flow, ["graph", _graph_file(tmp_path), "-o", str(out)])
    assert result.exit_code == 0, result.stderr
    assert "<svg" in out.read_text()


def test_list_flows(runner, tmp_path, monkeypatch):
    import geenii.config
    import geenii.g

    user_dir, project_dir = tmp_path / "user", tmp_path / "project"
    user_dir.mkdir()
    project_dir.mkdir()
    for name in ("b.yaml", "a.toml", "notes.txt"):
        (user_dir / name).write_text("")
    (project_dir / "c.json").write_text("{}")
    dirs = lambda: [str(user_dir), str(project_dir), str(tmp_path / "missing")]
    monkeypatch.setattr(geenii.config, "flow_dirs", dirs)
    monkeypatch.setattr(geenii.g, "flow_dirs", dirs)

    result = runner.invoke(flow, ["list"])
    assert result.exit_code == 0, result.output
    lines = result.output.splitlines()
    assert [line.split()[0] for line in lines] == ["a", "b", "c"]
    assert lines[2].split()[1] == str(project_dir / "c.json")

    result = runner.invoke(flow, ["list", "--json"])
    assert json.loads(result.output)[0] == {
        "name": "a",
        "filepath": str(user_dir / "a.toml"),
    }


def test_list_flows_empty(runner, tmp_path, monkeypatch):
    import geenii.config
    import geenii.g

    monkeypatch.setattr(geenii.config, "flow_dirs", lambda: [str(tmp_path / "missing")])
    monkeypatch.setattr(geenii.g, "flow_dirs", lambda: [str(tmp_path / "missing")])
    result = runner.invoke(flow, ["list"])
    assert result.exit_code == 0
    assert result.output == f"No flows found in:\n  {tmp_path / 'missing'}\n"
