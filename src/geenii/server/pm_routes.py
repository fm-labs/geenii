"""
HTTP routes for the process manager.

Thin wrapper around ProcessManagerClient, which talks to the geenii daemon over
its Unix socket. The client is synchronous, so the endpoints are plain `def`
functions and FastAPI runs them in its threadpool.
"""
from __future__ import annotations

from typing import Literal, Optional

import pydantic
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from geenii.pm.process_manager_client import ProcessManagerClient

router = APIRouter(prefix="/pm", tags=["pm"])

# Daemon error messages are "<ExceptionType>: <message>"; map the type to an HTTP status
_ERROR_STATUS = {
    "KeyError": 404,
    "ValueError": 400,
    "TimeoutError": 408,
    "RuntimeError": 409,
}


class StartProcessRequest(pydantic.BaseModel):
    command: str | list[str] = pydantic.Field(
        ..., description="A string runs through the shell; a list is executed directly")
    env: Optional[dict[str, str]] = pydantic.Field(None, description="Extra environment variables")
    cwd: Optional[str] = pydantic.Field(None, description="Working directory")
    pid: Optional[str] = pydantic.Field(None, description="Custom process ID (auto-generated if omitted)")


def dep_pm_client() -> ProcessManagerClient:
    return ProcessManagerClient()


def _call(fn, *args, **kwargs):
    """Invoke a client method, translating daemon and connection errors into HTTPExceptions."""
    try:
        return fn(*args, **kwargs)
    except RuntimeError as exc:
        message = str(exc)
        exc_type, _, detail = message.partition(": ")
        if exc_type == "KeyError":
            detail = detail.strip("'\"")  # str(KeyError) quotes its message
        raise HTTPException(status_code=_ERROR_STATUS.get(exc_type, 500), detail=detail or message)
    except OSError as exc:
        raise HTTPException(status_code=503,
                            detail=f"Process manager is not reachable (is `geenii daemon start` running?): {exc}")


@router.get("/ping")
def ping(client: ProcessManagerClient = Depends(dep_pm_client)) -> dict:
    """Check if the geenii daemon (which hosts the process manager) is running."""
    if not client.is_available():
        raise HTTPException(status_code=503, detail="Process manager is not reachable")
    return {"ok": True}


@router.get("/processes")
def list_processes(include_finished: bool = Query(False, description="Include finished processes from disk"),
                   client: ProcessManagerClient = Depends(dep_pm_client)) -> list[dict]:
    """List background processes."""
    return _call(client.list, include_finished=include_finished)


@router.post("/processes", status_code=201)
def start_process(request: StartProcessRequest,
                  client: ProcessManagerClient = Depends(dep_pm_client)) -> dict:
    """Start a background process."""
    return _call(client.start, request.command, env=request.env, cwd=request.cwd, pid=request.pid)


@router.get("/processes/{process_id}")
def get_process(process_id: str, client: ProcessManagerClient = Depends(dep_pm_client)) -> dict:
    """Get the current state of a background process."""
    return _call(client.status, process_id)


@router.get("/processes/{process_id}/output", response_class=PlainTextResponse)
def get_process_output(process_id: str,
                       stream: Literal["stdout", "stderr"] = "stdout",
                       tail: Optional[int] = Query(None, ge=0, description="Return only the last N lines"),
                       offset: Optional[int] = Query(None, ge=0, description="Start reading at this byte position"),
                       limit: Optional[int] = Query(None, ge=1, description="Read at most this many bytes"),
                       client: ProcessManagerClient = Depends(dep_pm_client)) -> str:
    """Get the captured output of a background process.

    Either the last `tail` lines, or `limit` bytes from byte `offset`. To read the whole
    output in chunks, advance offset by limit until the response body is empty.
    """
    return _call(client.output, process_id, stream=stream, tail=tail, offset=offset, limit=limit)


@router.post("/processes/{process_id}/wait")
def wait_process(process_id: str,
                 timeout: Optional[float] = Query(None, gt=0, description="Give up after this many seconds"),
                 client: ProcessManagerClient = Depends(dep_pm_client)) -> dict:
    """Wait until a background process has finished and return its final state."""
    return _call(client.wait, process_id, timeout=timeout)


@router.post("/processes/{process_id}/kill")
def kill_process(process_id: str,
                 force: bool = Query(False, description="Send SIGKILL instead of SIGTERM"),
                 client: ProcessManagerClient = Depends(dep_pm_client)) -> dict:
    """Kill a running background process."""
    return _call(client.kill, process_id, force=force)


@router.delete("/processes/{process_id}", status_code=204)
def cleanup_process(process_id: str, client: ProcessManagerClient = Depends(dep_pm_client)) -> None:
    """Remove on-disk logs for a finished process."""
    _call(client.cleanup, process_id)
