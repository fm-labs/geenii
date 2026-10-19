import os
import subprocess
import sys

import pytest

from geenii import tools
from geenii.tool.common import ToolCallContext, expand_vars
from geenii.tool.computer import AppleScriptTool, ComputerTool
from geenii.tool.registry import ToolRegistry
from geenii.tools import init_builtin_tools

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="runs POSIX shell commands")

# for the tests that don't care about the working dir
CTX = ToolCallContext(cwd=os.getcwd())


@pytest.fixture
def bash():
    return ComputerTool(name="bash")


@pytest.fixture
def recorded_run(monkeypatch):
    """Replace subprocess.run; records each call and returns a successful, empty result."""
    calls = []

    def fake_run(command, **kwargs):
        calls.append({"command": command, **kwargs})
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    return calls


# ---------- output ----------

def test_stdout_and_stderr_are_in_text(bash):
    result = bash.invoke(ctx=CTX, args={"command": "echo out; echo err >&2"})
    assert result.text == "stdout:\nout\nstderr:\nerr"
    assert result.is_error is False


def test_output_is_stripped(bash):
    assert bash.invoke(ctx=CTX, args={"command": "printf '\\n  out  \\n\\n'"}).text == "stdout:\nout\nstderr:\n"


def test_json_object_output_is_structured_content(bash):
    result = bash.invoke(ctx=CTX, args={"command": """echo '{"a": 1, "b": [true]}'"""})
    assert result.structured_content == {"a": 1, "b": [True]}
    assert result.is_error is False


@pytest.mark.parametrize("output", ["5", "[1, 2]", '"text"', "true"])
def test_json_non_object_output_is_not_structured_content(bash, output):
    assert bash.invoke(ctx=CTX, args={"command": f"echo '{output}'"}).structured_content is None


def test_non_json_output_has_no_structured_content(bash):
    assert bash.invoke(ctx=CTX, args={"command": "echo hello"}).structured_content is None


def test_non_zero_exit_is_an_error(bash):
    result = bash.invoke(ctx=CTX, args={"command": "echo partial; echo boom >&2; exit 3"})
    assert result.is_error is True
    assert result.text == "stdout:\npartial\nstderr:\nboom\nEXITED WITH NON-ZERO EXIT CODE: 3"


def test_error_result_has_no_structured_content_even_for_json(bash):
    result = bash.invoke(ctx=CTX, args={"command": """echo '{"a": 1}'; exit 1"""})
    assert result.is_error is True
    assert result.structured_content is None


def test_unknown_command_is_an_error(bash):
    result = bash.invoke(ctx=CTX, args={"command": "geenii-no-such-command-xyz"})
    assert result.is_error is True
    assert "EXITED WITH NON-ZERO EXIT CODE: 127" in result.text


def test_runs_through_the_shell(bash):
    assert bash.invoke(ctx=CTX, args={"command": "echo a | tr a b && echo c"}).text.startswith("stdout:\nb\nc\n")


def test_unbalanced_quote_reaches_the_shell(bash):
    result = bash.invoke(ctx=CTX, args={"command": "echo it's"})
    # the shell's own syntax error, not a Python exception
    assert result.is_error is True


# ---------- arguments ----------

@pytest.mark.parametrize("args", [{}, {"command": ""}, {"command": None}, {"other": "x"}])
def test_missing_command_raises(bash, args):
    with pytest.raises(ValueError, match="Missing 'command'"):
        bash.invoke(ctx=CTX, args=args)


def test_command_template(recorded_run):
    tool = ComputerTool(name="t", command_template="git -C {repo} {command}")
    tool.invoke(ctx=CTX, args={"command": "status --short", "repo": "/src"})
    assert recorded_run[0]["command"] == "git -C /src status --short"


def test_command_template_with_missing_arg_raises(recorded_run):
    tool = ComputerTool(name="t", command_template="git -C {repo} {command}")
    with pytest.raises(KeyError):
        tool.invoke(ctx=CTX, args={"command": "status"})
    assert recorded_run == []


def test_braces_in_command_are_kept_with_template(recorded_run):
    tool = ComputerTool(name="t", command_template="sh -c {command}")
    tool.invoke(ctx=CTX, args={"command": "echo {x}"})
    assert recorded_run[0]["command"] == "sh -c echo {x}"


def test_applescript_template(recorded_run):
    AppleScriptTool(name="as").invoke(ctx=CTX, args={"command": 'display dialog "hi"'})
    assert recorded_run[0]["command"] == """osascript -e 'display dialog "hi"'"""


# ---------- working dir ----------

def test_runs_in_given_cwd(bash, tmp_path):
    assert bash.invoke(args={"command": "pwd -P"}, ctx=ToolCallContext(cwd=str(tmp_path))).text.startswith(
        f"stdout:\n{os.path.realpath(tmp_path)}\n")


def test_invoke_tool_defaults_to_geenii_working_dir(bash, tmp_path, monkeypatch):
    monkeypatch.setattr(tools, "GEENII_WORKING_DIR", str(tmp_path))
    monkeypatch.setattr(tools, "append_jsonl", lambda path, data: None)
    result = tools.invoke_tool(bash, args={"command": "pwd -P"}, env={})
    assert result.text.startswith(f"stdout:\n{os.path.realpath(tmp_path)}\n")


def test_missing_cwd_raises(bash, tmp_path):
    with pytest.raises(FileNotFoundError):
        bash.invoke(args={"command": "pwd"}, ctx=ToolCallContext(cwd=str(tmp_path / "missing")))


# ---------- env ----------

def test_env_is_added_to_the_process_environment(bash, monkeypatch):
    monkeypatch.setenv("GEENII_TEST_INHERITED", "inherited")
    result = bash.invoke(ctx=CTX, args={"command": 'echo "$GEENII_TEST_EXTRA"; echo "$GEENII_TEST_INHERITED"'},
                         env={"GEENII_TEST_EXTRA": "extra"})
    assert result.text.startswith("stdout:\nextra\ninherited\n")


def test_env_overrides_the_process_environment(bash, monkeypatch):
    monkeypatch.setenv("GEENII_TEST_VAR", "old")
    result = bash.invoke(ctx=CTX, args={"command": "printenv GEENII_TEST_VAR"}, env={"GEENII_TEST_VAR": "new"})
    assert result.text.startswith("stdout:\nnew\n")


def test_env_does_not_change_os_environ(bash):
    bash.invoke(ctx=CTX, args={"command": "true"}, env={"GEENII_TEST_LEAK": "x"})
    assert "GEENII_TEST_LEAK" not in os.environ


def test_env_vars_are_expanded_in_the_command(recorded_run, bash):
    bash.invoke(ctx=CTX, args={"command": "echo ${NAME} $NAME $OTHER"}, env={"NAME": "geenii"})
    # unknown variables are left to the shell
    assert recorded_run[0]["command"] == "echo geenii geenii $OTHER"


def test_expand_vars():
    assert expand_vars("${A}/$B/${C}", {"A": "a", "B": "b"}) == "a/b/${C}"


def test_expand_vars_does_not_replace_prefixes():
    assert expand_vars("$AB ${A}B $A", {"A": "x", "AB": "y"}) == "y xB x"
    assert expand_vars("$AB", {"A": "x"}) == "$AB"


def test_expand_vars_does_not_expand_values_again():
    assert expand_vars("$A", {"A": "$B", "B": "b"}) == "$B"


# ---------- registered tools ----------

def test_builtin_bash_tool():
    registry = ToolRegistry()
    init_builtin_tools(registry)
    assert registry.get("bash").invoke(ctx=CTX, args={"command": "echo hi"}).text.startswith("stdout:\nhi\n")


def test_builtin_python_tool():
    registry = ToolRegistry()
    init_builtin_tools(registry)
    result = registry.get("python").invoke(ctx=CTX, args={"command": "-c 'print(42)'"})
    assert result.is_error is False
    assert result.text.startswith("stdout:\n42\n")
