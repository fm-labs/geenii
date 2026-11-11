"""
HTTP routes for the geenii daemon (process manager, scheduler, supervisor host).

The DaemonClient is synchronous, so the endpoints are plain `def` functions and
FastAPI runs them in its threadpool.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from geenii.daemon.client import DaemonClient

router = APIRouter(prefix="/daemon", tags=["daemon"])


def dep_daemon_client() -> DaemonClient:
    return DaemonClient()


@router.get("/status")
def daemon_status(client: DaemonClient = Depends(dep_daemon_client)) -> dict:
    """Whether the geenii daemon is running, and what it hosts if it is.

    Always answers 200; `running` is false when the daemon socket is not reachable.
    """
    result = {"running": False, "socket": client.socket_path, "info": None, "error": None}
    if not client.is_available():
        result["error"] = "The geenii daemon is not running (start it with `geenii daemon start`)"
        return result
    try:
        result["info"] = client.info()
        result["running"] = True
    except (RuntimeError, OSError) as exc:
        # The daemon went away between the ping and the info call, or answered with an error
        result["error"] = str(exc)
    return result
