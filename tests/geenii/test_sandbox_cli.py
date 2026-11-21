import os
import subprocess

import pytest
from click.testing import CliRunner

from geenii import config
from geenii.cli import sandbox_cli
from geenii.sandbox import Sandbox


@pytest.fixture
def runs(monkeypatch, tmp_path):
    """Fake docker: records the sandboxes built and run instead of calling docker"""
    monkeypatch.setattr(config, "GEENII_CACHE_DIR", str(tmp_path / ".cache"))
    monkeypatch.setattr(sandbox_cli.shutil, "which", lambda _: "/usr/bin/docker")
    calls = []

    def build(self):
        self.image_name = "geenii-sandbox-" + self.sandbox_id

    def run(self):
        calls.append(self)
        return 3, "out\n", "err"

    monkeypatch.setattr(Sandbox, "build", build)
    monkeypatch.setattr(Sandbox, "run", run)
    return calls


@pytest.fixture
def app_dir(tmp_path):
    path = tmp_path / "My App"
    path.mkdir()
    (path / "main.py").write_text("")
    (path / "run.sh").write_text("")
    return str(path)


def _invoke(*args, env=None):
    return CliRunner().invoke(sandbox_cli.sandbox, list(args), env=env)


def test_run_python_passes_options_and_exit_code(runs, app_dir):
    result = _invoke(
        "run", "python", app_dir, "main.py", "-e", "A=1", "-e", "B", "--network", "bridge", "-t", "60",
        "--memory", "1g", "-m", "/data:/data:ro", "--cap-add", "NET_RAW", "--", "--flag", "-t", "x",
        env={"B": "from-env"},
    )
    assert result.exit_code == 3, result.output
    assert "out\n" in result.stdout and result.stderr.endswith("err\n")
    (box,) = runs
    assert type(box).__name__ == "PythonSandbox"
    assert box.command() == ["python3", "main.py", "--flag", "-t", "x"]
    assert box.env == {"A": "1", "B": "from-env"}
    assert (box.network_mode, box.timeout, box.mem_limit) == ("bridge", 60, "1g")
    assert box.mounts == ["/data:/data:ro"] and box.cap_add == ["NET_RAW"]
    assert box.app_dir == os.path.realpath(app_dir)
    assert box.sandbox_id == sandbox_cli.default_sandbox_id("python", app_dir)
    assert box.sandbox_id.startswith("python-my-app-")


def test_run_defaults(runs, app_dir):
    assert _invoke("run", "python", app_dir).exit_code == 3
    (box,) = runs
    assert box.command() == ["python3", "main.py"]
    assert (box.network_mode, box.cpu_limit, box.mem_limit, box.pid_limit, box.timeout) == ("none", 0.5, "256m", 100, 30)
    assert box.env is None and box.mounts is None


def test_run_bash_command_and_script(runs, app_dir):
    assert _invoke("run", "bash", app_dir, "-c", "ls /app").exit_code == 3
    assert _invoke("run", "bash", app_dir, "run.sh", "a").exit_code == 3
    assert [b.command() for b in runs] == [["bash", "-c", "ls /app"], ["bash", "run.sh", "a"]]


@pytest.mark.parametrize(
    "args, message",
    [
        (["run", "python", "{app}", "-c", "ls"], "only supported for the bash runtime"),
        (["run", "bash", "{app}", "run.sh", "-c", "ls"], "mutually exclusive"),
        (["run", "bash", "{app}"], "bash needs a SCRIPT or --command"),
        (["run", "python", "{app}", "missing.py"], "Script not found"),
        (["run", "python", "{app}", "-e", "1BAD=x"], "invalid variable name"),
        (["run", "python", "{app}", "-e", "UNSET_SANDBOX_TEST_VAR"], "is not set"),
        (["run", "python", "{app}", "--id", "Bad/Id"], "--id"),
    ],
)
def test_run_rejects_bad_input(runs, app_dir, args, message):
    result = _invoke(*[a.format(app=app_dir) for a in args])
    assert result.exit_code == 2 and message in result.output
    assert runs == []


def _fake_docker(monkeypatch, images, failing=()):
    calls = []

    def docker(*args):
        calls.append(args)
        if args[0] == "images":
            out = "".join(f"geenii-sandbox-{i}\t10MB\t1 day ago\n" for i in images)
            return subprocess.CompletedProcess(args, 0, out, "")
        rc = 1 if args[1].removeprefix("geenii-sandbox-") in failing else 0
        return subprocess.CompletedProcess(args, rc, "", "No such image" if rc else "")

    monkeypatch.setattr(sandbox_cli, "_docker", docker)
    return calls


def test_list(monkeypatch):
    _fake_docker(monkeypatch, ["python-a-1", "bash-b-2"])
    result = _invoke("list")
    assert result.exit_code == 0
    assert "python-a-1" in result.output and "bash-b-2" in result.output and "10MB" in result.output
    _fake_docker(monkeypatch, [])
    assert "No sandbox images" in _invoke("list").output


def test_rm_removes_images_and_cached_dockerfiles(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GEENII_CACHE_DIR", str(tmp_path))
    for sid in ("python-a-1", "bash-b-2"):
        os.makedirs(tmp_path / "sandboxes" / sid)
    calls = _fake_docker(monkeypatch, ["python-a-1", "bash-b-2"])

    result = _invoke("rm", "--all")
    assert result.exit_code == 0, result.output
    assert ("rmi", "geenii-sandbox-python-a-1") in calls and ("rmi", "geenii-sandbox-bash-b-2") in calls
    assert os.listdir(tmp_path / "sandboxes") == []


def test_rm_reports_failures(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "GEENII_CACHE_DIR", str(tmp_path))
    calls = _fake_docker(monkeypatch, [], failing=("gone",))
    result = _invoke("rm", "gone", "../escape")
    assert result.exit_code == 1
    assert "No such image" in result.output and "Invalid sandbox id: ../escape" in result.output
    assert calls == [("rmi", "geenii-sandbox-gone")]
    assert _invoke("rm").exit_code == 2
    assert _invoke("rm", "x", "--all").exit_code == 2


def test_sandbox_run_kills_the_container_on_timeout(monkeypatch, tmp_path):
    from geenii import sandbox as sandbox_mod

    monkeypatch.setattr(sandbox_mod, "run_docker_subprocess", lambda *a, **k: (-1, "", "Command timed out after 1 seconds"))
    killed = []
    monkeypatch.setattr(sandbox_mod.subprocess, "run", lambda cmd, **k: killed.append(cmd))
    box = sandbox_mod.BashSandbox(str(tmp_path), shell_command="sleep 9", sandbox_id="t", env={"SECRET": "v"})
    box.image_name = "geenii-sandbox-t"
    assert box.run()[0] == -1
    assert killed == [["docker", "rm", "-f", "geenii-sandbox-t"]]


def test_sandbox_env_values_stay_out_of_the_docker_argv(monkeypatch, tmp_path):
    from geenii import sandbox as sandbox_mod

    seen = {}
    monkeypatch.setattr(sandbox_mod, "run_docker_subprocess", lambda cmd, timeout, env=None: seen.update(cmd=cmd, env=env) or (0, "", ""))
    box = sandbox_mod.BashSandbox(str(tmp_path), shell_command="true", sandbox_id="t", env={"SECRET": "v"})
    box.image_name = "geenii-sandbox-t"
    box.run()
    assert "v" not in seen["cmd"] and "SECRET=v" not in seen["cmd"]
    assert seen["cmd"][seen["cmd"].index("SECRET") - 1] == "-e" and seen["env"] == {"SECRET": "v"}
    assert seen["cmd"][seen["cmd"].index("--tmpfs") + 1] == "/tmp"
