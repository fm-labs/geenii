import pytest
from click.testing import CliRunner

from geenii.cli import agent_cli as agent_cli_module


@pytest.fixture
def captured_run(monkeypatch):
    """Replace the actual agent run; record the arguments it would get."""
    calls = []
    monkeypatch.setattr(agent_cli_module, "agent_run", lambda **kw: calls.append(kw))
    monkeypatch.setattr(agent_cli_module, "dump_last_context_id", lambda *a, **kw: None)
    return calls


def _run(args, stdin):
    result = CliRunner().invoke(agent_cli_module.agent_cli, args, input=stdin)
    assert result.exit_code == 0, result.output
    return result


def test_prompt_argument_ignores_piped_stdin(captured_run):
    # A scheduled task inherits a non-TTY stdin; with a prompt given it must not be read
    _run(["-n", "dice", "Roll a dice"], stdin="from stdin")
    assert captured_run[0]["prompt"] == "Roll a dice"


def test_no_prompt_reads_piped_stdin(captured_run):
    _run(["-n", "dice"], stdin="Roll a dice")
    assert captured_run[0]["prompt"] == "Roll a dice"


def test_dash_prompt_reads_piped_stdin(captured_run):
    _run(["-n", "dice", "-"], stdin="Roll a dice")
    assert captured_run[0]["prompt"] == "Roll a dice"
