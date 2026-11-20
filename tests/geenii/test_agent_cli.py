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


@pytest.fixture
def last_context(monkeypatch):
    """A previous conversation 'ctx-last' to restore."""
    monkeypatch.setattr(agent_cli_module, "restore_last_context_id", lambda name: "ctx-last")


@pytest.mark.parametrize(("answer", "restored"), [("y", True), ("n", False), ("", False)])
def test_interactive_asks_to_restore_the_last_conversation(captured_run, last_context, answer, restored):
    result = _run(["-n", "dice", "-i", "Roll a dice"], stdin=f"{answer}\n")
    assert "Want to restore last conversation? (ctx-last)" in result.output
    context_id = captured_run[0]["context_id"]
    assert (context_id == "ctx-last") is restored
    if not restored:
        assert context_id.endswith("-cli")


def test_resume_restores_without_asking(captured_run, last_context):
    result = _run(["-n", "dice", "-i", "-r", "Roll a dice"], stdin="")
    assert "Want to restore" not in result.output
    assert captured_run[0]["context_id"] == "ctx-last"


def test_explicit_context_wins(captured_run, last_context):
    result = _run(["-n", "dice", "-i", "-r", "-c", "ctx-given", "Roll a dice"], stdin="")
    assert "Want to restore" not in result.output
    assert captured_run[0]["context_id"] == "ctx-given"


def test_new_conversation_when_nothing_to_restore(captured_run, monkeypatch):
    monkeypatch.setattr(agent_cli_module, "restore_last_context_id", lambda name: None)
    result = _run(["-n", "dice", "-i", "-r", "Roll a dice"], stdin="")
    assert "Want to restore" not in result.output
    assert captured_run[0]["context_id"].endswith("-cli")
