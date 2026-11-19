"""
Shared helpers for HTTP routes that talk to the geenii daemon.

- `dep_daemon_client`: the FastAPI dependency for a DaemonClient (override it in tests)
- `daemon_call`: call a daemon method, mapping "not running" and daemon errors to HTTP errors
- `daemon_errors`: the same error mapping, as a context manager around any client call
- `daemon_config_path`, `daemon_state`, `config_path`, `reload_config`: for routes that
  edit a config file the daemon may be using (scheduler, supervisor)

The DaemonClient is synchronous, so routes using it are plain `def` functions and
FastAPI runs them in its threadpool.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, Literal

from fastapi import HTTPException

from geenii.daemon.client import DaemonClient

DAEMON_NOT_RUNNING = "The geenii daemon is not running (start it with `geenii daemon start`)"

# Daemon errors are "<ExceptionType>: <message>"; the type picks the HTTP status (other types: 409)
ERROR_STATUS = {
    "KeyError": 404,
    "ValueError": 400,
    "TimeoutError": 408,
}

ConfigComponent = Literal["scheduler", "supervisor"]


def dep_daemon_client() -> DaemonClient:
    return DaemonClient(actor="api")


@contextmanager
def daemon_errors(not_found: str | None = None) -> Iterator[None]:
    """Translate errors of a daemon call into HTTPExceptions.

    - "<ExceptionType>: <message>" from a daemon handler: by ERROR_STATUS, else 409,
      with the message as detail (`not_found` replaces the detail of a KeyError)
    - other daemon errors (e.g. "Unknown method: x"): 500 with the full message
    - connection errors: 503
    """
    try:
        yield
    except RuntimeError as exc:
        message = str(exc)
        exc_type, sep, detail = message.partition(": ")
        if not sep or not exc_type.isidentifier():
            raise HTTPException(500, message)
        if exc_type == "KeyError":
            detail = not_found or detail.strip("'\"")  # str(KeyError) quotes its message
        raise HTTPException(ERROR_STATUS.get(exc_type, 409), detail or message)
    except OSError as exc:
        raise HTTPException(503, f"The geenii daemon is not reachable: {exc}")


def daemon_call(
    client: DaemonClient,
    method: str,
    params: dict | None = None,
    *,
    not_found: str | None = None,
) -> Any:
    """Call a method of the running daemon; 409 if it isn't running, other errors as in `daemon_errors`."""
    if not client.is_available():
        raise HTTPException(409, DAEMON_NOT_RUNNING)
    with daemon_errors(not_found):
        return client.call(method, params)


def daemon_config_path(client: DaemonClient, component: ConfigComponent) -> str | None:
    """The config file the running daemon uses for COMPONENT; None if it has none or isn't reachable."""
    if not client.is_available():
        return None
    try:
        return client.info()[component].get("config")
    except RuntimeError, OSError, KeyError:
        return None


def daemon_state(client: DaemonClient, component: ConfigComponent) -> tuple[dict | None, str | None, str | None]:
    """(COMPONENT status, config path the daemon uses, error); the status is None when the daemon is unreachable."""
    if not client.is_available():
        return None, None, None
    try:
        config = client.info()[component].get("config")
        return client.call(f"{component}.status"), config, None
    except (RuntimeError, OSError, KeyError) as exc:
        return None, None, str(exc)


def config_path(client: DaemonClient, component: ConfigComponent, default_path: str) -> tuple[str, bool]:
    """(config path to edit, whether a running daemon applies it): the daemon's file, else DEFAULT_PATH."""
    daemon_config = daemon_config_path(client, component)
    if daemon_config:
        return daemon_config, True
    return default_path, False


def reload_config(client: DaemonClient, component: ConfigComponent, live: bool) -> dict:
    """Make the daemon re-read COMPONENT's config file if it uses it; the file change stands either way."""
    if not live:
        return {"reloaded": False, "changes": None, "error": None}
    try:
        return {"reloaded": True, "changes": client.call(f"{component}.reload"), "error": None}
    except (RuntimeError, OSError) as exc:
        return {"reloaded": False, "changes": None, "error": str(exc)}
