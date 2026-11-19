"""Tests for `geenii server start/stop/status`.

The unit tests never start a server. The lifecycle tests run a real uvicorn server
in a child process, isolated from the user's home, cache and working directory.
"""

import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import time

import click
import psutil
import pytest
from click.testing import CliRunner

from geenii.cli import server_cli
from geenii.cli.server_cli import Endpoint, server


@pytest.fixture
def short_dir():
    # Unix socket paths are limited to ~104 bytes on macOS; pytest's tmp_path is often longer
    d = tempfile.mkdtemp(prefix="gs", dir="/tmp" if os.path.isdir("/tmp") else None)
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def env(short_dir, monkeypatch):
    """Point the CLI (and any server it spawns) at a throwaway home, cache and working dir."""
    home = os.path.join(short_dir, "home")
    cache = os.path.join(short_dir, "cache")
    work = os.path.join(short_dir, "work")
    for d in (home, cache, work):
        os.makedirs(d)
    monkeypatch.setattr(server_cli, "STATE_FILE", os.path.join(cache, "server.json"))
    monkeypatch.setattr(server_cli, "DEFAULT_LOG_FILE", os.path.join(cache, "logs", "server.log"))
    monkeypatch.setattr(server_cli, "DEFAULT_SOCKET", os.path.join(cache, "server.sock"))
    variables = {
        "HOME": home,
        "GEENII_CACHE_DIR": cache,
        "GEENII_WORKING_DIR": work,
        "GEENII_SERVER_SOCKET": None,
        "GEENII_SERVER_HOST": None,
        "GEENII_SERVER_PORT": None,
    }
    for key, value in variables.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    return {"home": home, "cache": cache, "work": work, "dir": short_dir}


@pytest.fixture
def cli(env):
    def invoke(*args):
        return CliRunner().invoke(server, list(args), env={"COLUMNS": "250"})

    yield invoke
    # Never leave a server behind, even when a test fails half-way.
    # (Some tests record the test process itself as the server; never signal that.)
    state = server_cli._read_state()
    proc = server_cli._running_process(state)
    if proc is not None and proc.pid != os.getpid():
        invoke("stop", "--timeout", "5")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until(predicate, timeout: float = 30.0, interval: float = 0.1) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


# --- unit tests -----------------------------------------------------------------


def test_endpoint_urls():
    assert Endpoint(host="127.0.0.1", port=8080).url == "http://127.0.0.1:8080"
    assert Endpoint(host="0.0.0.0", port=8080).url == "http://127.0.0.1:8080"
    assert Endpoint(host="::1", port=8080).url == "http://[::1]:8080"
    uds = Endpoint(uds="/run/geeniid.sock")
    assert uds.url == "http://localhost"
    assert str(uds) == "unix:/run/geeniid.sock"
    assert Endpoint.from_state({"uds": "/x.sock", "host": None, "port": None}) == Endpoint(uds="/x.sock")


def test_status_and_stop_without_server(cli):
    result = cli("status")
    assert result.exit_code == 1
    assert "not running" in result.output

    result = cli("status", "--json")
    assert result.exit_code == 1
    assert json.loads(result.output) == {"running": False}

    result = cli("stop")
    assert result.exit_code == 1
    assert "not running" in result.output


def test_stale_state_file_is_cleared(cli):
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    os.makedirs(os.path.dirname(server_cli.STATE_FILE), exist_ok=True)
    with open(server_cli.STATE_FILE, "w") as f:
        json.dump({"pid": dead.pid, "create_time": time.time(), "host": "127.0.0.1", "port": 1}, f)

    result = cli("status")
    assert result.exit_code == 1
    assert not os.path.exists(server_cli.STATE_FILE)


def test_reused_pid_is_not_mistaken_for_the_server(cli):
    # Our own PID, but with a create time from long ago: a different process.
    os.makedirs(os.path.dirname(server_cli.STATE_FILE), exist_ok=True)
    with open(server_cli.STATE_FILE, "w") as f:
        json.dump({"pid": os.getpid(), "create_time": 1.0, "host": "127.0.0.1", "port": 1}, f)

    assert cli("stop").exit_code == 1
    assert psutil.pid_exists(os.getpid())


def test_start_refuses_when_a_server_is_running(cli):
    server_cli._write_state(os.getpid(), Endpoint(host="127.0.0.1", port=1), None)

    result = cli("start", "--detach", "--port", str(_free_port()))
    assert result.exit_code == 1
    assert "already running" in result.output
    assert server_cli._read_state()["pid"] == os.getpid()


def test_uds_cannot_be_combined_with_host_or_port(cli):
    result = cli("start", "--uds", "/tmp/x.sock", "--port", "9000")
    assert result.exit_code == 2
    assert "--uds can't be combined with --port" in result.output


def test_bind_unix_socket_is_owner_only_and_replaces_a_stale_socket(env):
    path = os.path.join(env["dir"], "s.sock")
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(path)
    stale.close()  # file stays, nothing listens

    sock = server_cli._bind_unix_socket(path)
    try:
        assert stat.S_ISSOCK(os.stat(path).st_mode)
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    finally:
        sock.close()


def test_bind_unix_socket_refuses_a_regular_file(env):
    path = os.path.join(env["dir"], "not-a-socket")
    with open(path, "w") as f:
        f.write("keep me")

    with pytest.raises(click.ClickException, match="not a socket"):
        server_cli._bind_unix_socket(path)
    assert open(path).read() == "keep me"


# --- lifecycle tests (real server) -------------------------------------------------


def test_detached_tcp_lifecycle(cli):
    port = _free_port()

    result = cli("start", "--detach", "--port", str(port))
    assert result.exit_code == 0, result.output
    assert f"http://127.0.0.1:{port}" in result.output
    pid = server_cli._read_state()["pid"]

    result = cli("status", "--json")
    assert result.exit_code == 0, result.output
    info = json.loads(result.output)
    assert info["running"] and info["healthy"]
    assert info["pid"] == pid
    assert info["port"] == port
    assert info["uds"] is None

    result = cli("start", "--detach", "--port", str(_free_port()))
    assert result.exit_code == 1
    assert "already running" in result.output

    result = cli("stop")
    assert result.exit_code == 0, result.output
    assert not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    assert not os.path.exists(server_cli.STATE_FILE)
    assert not server_cli._is_healthy(Endpoint(host="127.0.0.1", port=port))


def test_detached_uds_lifecycle(cli, env):
    sock_path = server_cli.DEFAULT_SOCKET

    result = cli("start", "--detach", "--uds")  # no path: the default socket
    assert result.exit_code == 0, result.output
    assert f"unix:{sock_path}" in result.output
    assert stat.S_IMODE(os.stat(sock_path).st_mode) == 0o600

    info = json.loads(cli("status", "--json").output)
    assert info["healthy"]
    assert info["uds"] == sock_path
    assert info["host"] is None and info["port"] is None

    result = cli("stop")
    assert result.exit_code == 0, result.output
    assert not os.path.exists(sock_path)
    assert not os.path.exists(server_cli.STATE_FILE)


def test_detached_uds_with_reload_serves_and_stops_the_worker(cli, env):
    # With --reload uvicorn serves from a spawned worker process that inherits our socket fd.
    sock_path = os.path.join(env["dir"], "r.sock")

    result = cli("start", "--detach", "--reload", "--uds", sock_path)
    assert result.exit_code == 0, result.output
    parent = psutil.Process(server_cli._read_state()["pid"])
    workers = parent.children(recursive=True)
    assert workers

    assert cli("stop").exit_code == 0
    assert _wait_until(lambda: not any(w.is_running() and w.status() != psutil.STATUS_ZOMBIE for w in workers), 10)
    assert not os.path.exists(sock_path)


def test_foreground_uds_server_is_stopped_from_another_process(cli, env):
    sock_path = os.path.join(env["dir"], "fg.sock")
    proc = subprocess.Popen(
        [sys.executable, "-m", "geenii.cli.main", "server", "start", "--uds", sock_path],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        env=os.environ.copy(),
    )
    try:
        assert _wait_until(lambda: server_cli._is_healthy(Endpoint(uds=sock_path))), "server did not come up"
        assert server_cli._read_state()["pid"] == proc.pid

        result = cli("stop")
        assert result.exit_code == 0, result.output
        assert proc.wait(timeout=10) == 0  # graceful shutdown, not a kill
        assert not os.path.exists(sock_path)
        assert not os.path.exists(server_cli.STATE_FILE)
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


def test_detached_start_reports_a_startup_failure(cli):
    # Something that isn't a geenii server already holds the port.
    blocker = socket.socket()
    blocker.bind(("127.0.0.1", 0))
    blocker.listen()
    port = blocker.getsockname()[1]
    try:
        result = cli("start", "--detach", "--port", str(port), "--wait", "30")
    finally:
        blocker.close()

    assert result.exit_code == 1
    assert "exited during startup" in result.output
    assert not os.path.exists(server_cli.STATE_FILE)
