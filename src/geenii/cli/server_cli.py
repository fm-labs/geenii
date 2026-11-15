"""`geenii server`: start, stop and inspect the HTTP server (FastAPI API + web UI).

The running server is tracked in a state file (`$GEENII_CACHE_DIR/server.json`) holding
its PID, the process create time (so a reused PID is never mistaken for the server),
and where it listens (host/port or a Unix socket). `start` writes it in both foreground
and detached mode, so `stop` and `status` work from any terminal.
"""

import json
import logging
import os
import socket
import stat
import subprocess
import sys
import time
from dataclasses import asdict, dataclass

import click
import httpx
import psutil
from click.core import ParameterSource

from geenii.config import GEENII_CACHE_DIR

DEFAULT_HOST = os.getenv("GEENII_SERVER_HOST", "127.0.0.1")
DEFAULT_PORT = int(os.getenv("GEENII_SERVER_PORT", "33311"))
DEFAULT_SOCKET = os.path.join(GEENII_CACHE_DIR, "server.sock")
STATE_FILE = os.path.join(GEENII_CACHE_DIR, "server.json")
DEFAULT_LOG_FILE = os.path.join(GEENII_CACHE_DIR, "logs", "server.log")
HEALTH_PATH = "/api/v1/health"
APP_IMPORT = "geenii.server.server:app"
SOCKET_MODE = 0o600
_USE_DEFAULT_SOCKET = "\0default"  # `--uds` without a path; resolved to DEFAULT_SOCKET at call time


@dataclass(frozen=True)
class Endpoint:
    """Where the server listens: a Unix socket (`uds`) or host/port."""

    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    uds: str | None = None

    @classmethod
    def from_state(cls, state: dict) -> "Endpoint":
        return cls(host=state.get("host") or DEFAULT_HOST, port=state.get("port") or DEFAULT_PORT, uds=state.get("uds"))

    @property
    def url(self) -> str:
        """Base URL for requests (for a Unix socket, the host part is a placeholder)."""
        if self.uds:
            return "http://localhost"
        host = "127.0.0.1" if self.host in ("0.0.0.0", "", "::") else self.host
        if ":" in host:
            host = f"[{host}]"
        return f"http://{host}:{self.port}"

    def __str__(self) -> str:
        return f"unix:{self.uds}" if self.uds else self.url

    def client(self, timeout: float) -> httpx.Client:
        transport = httpx.HTTPTransport(uds=self.uds) if self.uds else None
        return httpx.Client(base_url=self.url, transport=transport, timeout=timeout)


# --- state file ---------------------------------------------------------------


def _read_state() -> dict | None:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_state(pid: int, endpoint: Endpoint, log_file: str | None) -> None:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    state = {
        "pid": pid,
        "create_time": psutil.Process(pid).create_time(),
        **asdict(endpoint),
        "log_file": log_file,
        "started_at": time.time(),
    }
    tmp = STATE_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_FILE)


def _remove_state(pid: int | None = None) -> None:
    """Remove the state file (only if it still belongs to `pid`, when given)."""
    if pid is not None:
        state = _read_state()
        if state and state.get("pid") != pid:
            return
    try:
        os.remove(STATE_FILE)
    except FileNotFoundError:
        pass


def _running_process(state: dict | None) -> psutil.Process | None:
    """The server process described by `state`, or None if it is gone (or the PID was reused)."""
    if not state or not state.get("pid"):
        return None
    try:
        proc = psutil.Process(state["pid"])
        if abs(proc.create_time() - state.get("create_time", 0)) > 1:
            return None
        if proc.status() == psutil.STATUS_ZOMBIE:
            return None
        return proc
    except psutil.Error:
        return None


def _current_server() -> tuple[dict | None, psutil.Process | None]:
    """(state, process) of the running server; clears a stale state file."""
    state = _read_state()
    proc = _running_process(state)
    if state and proc is None:
        _remove_state()
        state = None
    return state, proc


# --- helpers ------------------------------------------------------------------


def _is_healthy(endpoint: Endpoint, timeout: float = 1.0) -> bool:
    # Health probes are routine; keep httpx's per-request INFO lines out of the CLI output.
    httpx_logger = logging.getLogger("httpx")
    if httpx_logger.getEffectiveLevel() <= logging.INFO:
        httpx_logger.setLevel(logging.WARNING)
    if endpoint.uds and not os.path.exists(endpoint.uds):
        return False
    try:
        with endpoint.client(timeout) as client:
            return client.get(HEALTH_PATH).status_code == 200
    except httpx.HTTPError:
        return False


def _remove_socket_file(path: str | None) -> None:
    if path and os.path.exists(path) and stat.S_ISSOCK(os.stat(path).st_mode):
        os.remove(path)


def _bind_unix_socket(path: str) -> socket.socket:
    """Bind a listening Unix socket at `path`, readable/writable by the owner only.

    uvicorn's own `uds=` binding makes the socket world-writable (0666) and, with
    reload, refuses to start when a stale socket file exists; binding it here and
    handing uvicorn the fd avoids both.
    """
    if os.path.lexists(path):
        if not stat.S_ISSOCK(os.lstat(path).st_mode):
            raise click.ClickException(f"{path} exists and is not a socket.")
        if _is_healthy(Endpoint(uds=path)):
            raise click.ClickException(f"something is already serving unix:{path}.")
        os.remove(path)  # stale socket from a server that didn't shut down cleanly

    parent = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(parent):
        os.makedirs(parent, mode=0o700, exist_ok=True)

    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    old_umask = os.umask(0o177)  # no window in which the socket is group/world accessible
    try:
        sock.bind(path)
    except OSError as exc:
        sock.close()
        raise click.ClickException(f"cannot bind unix:{path}: {exc}") from exc
    finally:
        os.umask(old_umask)
    os.chmod(path, SOCKET_MODE)
    sock.set_inheritable(True)  # the --reload worker is a separate process
    return sock


def _self_command() -> list[str]:
    """Command that runs this CLI again (source install or a frozen/compiled binary)."""
    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        return [sys.executable]
    return [sys.executable, "-m", "geenii.cli.main"]


def _tail(path: str, lines: int = 20) -> str:
    try:
        with open(path, errors="replace") as f:
            return "".join(f.readlines()[-lines:])
    except OSError:
        return ""


# --- commands -----------------------------------------------------------------


@click.group()
def server():
    """Start, stop and inspect the geenii HTTP server (API + web UI)."""


@server.command(name="start")
@click.option("--host", default=DEFAULT_HOST, show_default=True, help="Bind address (env: GEENII_SERVER_HOST).")
@click.option(
    "--port", "-p", default=DEFAULT_PORT, type=int, show_default=True, help="Port (env: GEENII_SERVER_PORT)."
)
@click.option(
    "--uds",
    is_flag=False,
    flag_value=_USE_DEFAULT_SOCKET,
    default=None,
    envvar="GEENII_SERVER_SOCKET",
    help=f"Listen on a Unix socket instead of host/port (env: GEENII_SERVER_SOCKET). "
    f"Without a path: {DEFAULT_SOCKET}",
)
@click.option("--detach", "-d", is_flag=True, help="Run in the background and return once the server is up.")
@click.option("--reload", is_flag=True, help="Restart the server when source files change (development).")
@click.option(
    "--log-file",
    default=None,
    help=f"Where a detached server writes its output. Default: {DEFAULT_LOG_FILE}",
)
@click.option(
    "--wait",
    "wait_s",
    default=60.0,
    type=float,
    show_default=True,
    help="With --detach: seconds to wait for the server to become healthy.",
)
@click.pass_context
def start(ctx, host, port, uds, detach, reload, log_file, wait_s):
    """Run the server (in the foreground unless --detach)."""
    if uds:
        explicit = [
            f"--{name}"
            for name in ("host", "port")
            if ctx.get_parameter_source(name) == ParameterSource.COMMANDLINE
        ]
        if explicit:
            raise click.UsageError(f"--uds can't be combined with {' / '.join(explicit)}.")
        if uds == _USE_DEFAULT_SOCKET:
            uds = DEFAULT_SOCKET
        endpoint = Endpoint(uds=os.path.abspath(os.path.expanduser(uds)))
    else:
        endpoint = Endpoint(host=host, port=port)

    state, proc = _current_server()
    if proc is not None:
        click.echo(
            f"Error: the geenii server is already running (pid {proc.pid}, {Endpoint.from_state(state)}).",
            err=True,
        )
        raise SystemExit(1)

    if detach:
        _start_detached(endpoint, reload, log_file or DEFAULT_LOG_FILE, wait_s)
    else:
        _run_foreground(endpoint, reload, log_file)


def _run_foreground(endpoint: Endpoint, reload: bool, log_file: str | None) -> None:
    import uvicorn

    listen: dict = {"host": endpoint.host, "port": endpoint.port}
    sock = None
    if endpoint.uds:
        sock = _bind_unix_socket(endpoint.uds)
        listen = {"fd": sock.fileno()}

    pid = os.getpid()
    _write_state(pid, endpoint, log_file)
    click.echo(f"Starting geenii server on {endpoint} (pid {pid})")
    # --reload needs the import string. Otherwise pass the app object: a real import
    # statement is what PyInstaller follows, so the frozen build bundles geenii.server.
    app = APP_IMPORT
    if not reload:
        from geenii.server.server import app
    try:
        uvicorn.run(app, reload=reload, workers=1, log_level="info", **listen)
    finally:
        _remove_state(pid)
        if sock is not None:
            sock.close()
            _remove_socket_file(endpoint.uds)


def _start_detached(endpoint: Endpoint, reload: bool, log_file: str, wait_s: float) -> None:
    if _is_healthy(endpoint):
        click.echo(f"Error: something is already serving {endpoint}.", err=True)
        raise SystemExit(1)

    cmd = [*_self_command(), "server", "start", "--log-file", log_file]
    if endpoint.uds:
        cmd += ["--uds", endpoint.uds]
    else:
        cmd += ["--host", endpoint.host, "--port", str(endpoint.port)]
    if reload:
        cmd.append("--reload")

    os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
    with open(log_file, "ab") as log:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,  # survive the terminal closing; own process group
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

    deadline = time.monotonic() + wait_s
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            click.echo(f"Error: the server exited during startup (code {proc.returncode}).", err=True)
            click.echo(_tail(log_file), err=True)
            raise SystemExit(1)
        if _is_healthy(endpoint):
            click.echo(f"geenii server started (pid {proc.pid}): {endpoint}")
            click.echo(f"Logs: {log_file}")
            return
        time.sleep(0.25)

    click.echo(
        f"Warning: the server (pid {proc.pid}) did not answer on {endpoint} within {wait_s:g}s; "
        f"it may still be starting. Check {log_file}.",
        err=True,
    )
    raise SystemExit(1)


@server.command(name="stop")
@click.option(
    "--timeout", "-t", default=10.0, type=float, show_default=True, help="Seconds to wait before killing it."
)
def stop(timeout):
    """Stop the running server (SIGTERM, then SIGKILL after --timeout)."""
    state, proc = _current_server()
    if proc is None:
        click.echo("The geenii server is not running.")
        raise SystemExit(1)

    # With --reload, uvicorn's worker is a child of this process; take the whole tree.
    children = proc.children(recursive=True)
    proc.terminate()
    gone, alive = psutil.wait_procs([proc], timeout=timeout)
    if alive:
        click.echo(f"The server did not stop within {timeout:g}s; killing it.", err=True)
        for p in [proc, *children]:
            try:
                p.kill()
            except psutil.Error:
                pass
        psutil.wait_procs([proc], timeout=5)
    else:
        # Reap any leftover children (e.g. a reload worker) that outlived the parent.
        _, leftover = psutil.wait_procs(children, timeout=2)
        for p in leftover:
            try:
                p.kill()
            except psutil.Error:
                pass

    _remove_state(state["pid"])
    _remove_socket_file(state.get("uds"))  # only left behind if the server was killed
    click.echo(f"geenii server stopped (pid {state['pid']}).")


@server.command(name="status")
@click.option("--json", "as_json", is_flag=True, help="Print the status as JSON.")
def status(as_json):
    """Show whether the server is running and responding."""
    state, proc = _current_server()
    if proc is None:
        if as_json:
            click.echo(json.dumps({"running": False}))
        else:
            click.echo("The geenii server is not running.")
        raise SystemExit(1)

    endpoint = Endpoint.from_state(state)
    info = {
        "running": True,
        "healthy": _is_healthy(endpoint),
        "pid": state["pid"],
        "url": str(endpoint),
        "host": None if endpoint.uds else endpoint.host,
        "port": None if endpoint.uds else endpoint.port,
        "uds": endpoint.uds,
        "uptime_s": round(time.time() - proc.create_time()),
        "log_file": state.get("log_file"),
    }
    if as_json:
        click.echo(json.dumps(info, indent=2))
        return
    health = "healthy" if info["healthy"] else "not responding"
    click.echo(f"geenii server is running ({health})")
    click.echo(f"  pid:    {info['pid']}")
    click.echo(f"  url:    {info['url']}")
    click.echo(f"  uptime: {info['uptime_s']}s")
    if info["log_file"]:
        click.echo(f"  logs:   {info['log_file']}")
