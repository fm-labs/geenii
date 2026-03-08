from typing import Dict, List, Optional

from fastapi import Depends, HTTPException, Request, APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from geenii.server.deps import require_api_key
from geenii.supervisor import Supervisor


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class StartProcRequest(BaseModel):
    cmd: List[str] = Field(..., description="Command argv, e.g. ['python', '-m', 'worker']")
    restart: bool = Field(True, description="Auto-restart on unexpected exit")
    env: Optional[Dict[str, str]] = Field(
        None, description="Extra env vars merged into os.environ (not a replacement)"
    )
    cwd: Optional[str] = Field(None, description="Working directory")
    capture_output: bool = Field(True, description="Capture stdout/stderr into the log buffer")


class UpdateProcRequest(BaseModel):
    restart: Optional[bool] = None
    # Use Optional[Dict] where None means "clear this field"
    # We rely on model_fields_set to distinguish "not provided" from "set to null"
    env: Optional[Dict[str, str]] = Field(default=object())  # type: ignore[assignment]
    cwd: Optional[str] = Field(default_factory=object())  # type: ignore[assignment]

    model_config = {"arbitrary_types_allowed": True}


router = APIRouter(prefix="/supervisor", tags=["supervisor"])


def dep_supervisor(request: Request) -> Supervisor:
    return request.app.state.supervisor

# --- Status & logs ----------------------------------------------------------

@router.get("/status", dependencies=[Depends(require_api_key)])
async def supervisor_status(supervisor: Supervisor = Depends(dep_supervisor)):
    return supervisor.status()


@router.get("/logs/{name}", dependencies=[Depends(require_api_key)])
async def supervisor_logs(name: str, tail: int = 100, supervisor: Supervisor = Depends(dep_supervisor)):
    try:
        return {"name": name, "lines": supervisor.logs(name, tail=tail)}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown process: {name}")


@router.get("/logs/{name}/stream", dependencies=[Depends(require_api_key)])
async def supervisor_logs_stream(name: str, request: Request, supervisor: Supervisor = Depends(dep_supervisor)):
    """
    Server-Sent Events stream of plain-text log lines.
    Replays the existing buffer then delivers new lines in real time.
    Each SSE event data field is a single log line.
    """
    sup = supervisor
    if name not in sup._logs:
        raise HTTPException(status_code=404, detail=f"unknown process: {name}")

    async def event_generator():
        async for line in sup.stream_logs(name):
            if await request.is_disconnected():
                break
            if line == "":
                yield ": keepalive\n\n"
            else:
                safe = line.replace("\n", "\\n")
                yield f"data: {safe}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/logs/{name}/stream/jsonl", dependencies=[Depends(require_api_key)])
async def supervisor_logs_stream_jsonl(name: str, request: Request, supervisor: Supervisor = Depends(dep_supervisor)):
    """
    Server-Sent Events stream of structured JSONL log events.
    Replays the existing buffer then delivers new events in real time.
    Each SSE event data field is a JSON object:
      {"t": <unix float>, "name": "<proc>", "tag": "<stdout|stderr|supervisor>", "msg": "..."}
    """
    sup = supervisor
    if name not in sup._logs:
        raise HTTPException(status_code=404, detail=f"unknown process: {name}")

    async def event_generator():
        async for event in sup.stream_logs_jsonl(name):
            if await request.is_disconnected():
                break
            if event is None:
                yield ": keepalive\n\n"
            else:
                yield f"data: {event.as_json()}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


# --- Process management -----------------------------------------------------

# @router.post("/procs/{name}", dependencies=[Depends(require_auth)])
# async def start_or_replace_proc(name: str, req: StartProcRequest, supervisor: Supervisor = Depends(dep_supervisor)):
#     cfg = ProcConfig(
#         name=name,
#         cmd=req.cmd,
#         restart=req.restart,
#         env=req.env,
#         cwd=req.cwd,
#         capture_output=req.capture_output,
#     )
#     await supervisor.ensure(name, cfg)
#     return {"ok": True, "name": name}
#
#
# @router.patch("/procs/{name}", dependencies=[Depends(require_auth)])
# async def patch_proc(name: str, req: UpdateProcRequest, supervisor: Supervisor = Depends(dep_supervisor)):
#     try:
#         await supervisor.update_config(name, req)
#     except KeyError:
#         raise HTTPException(status_code=404, detail=f"unknown process: {name}")
#     return {"ok": True, "name": name}


@router.post("/procs/{name}/restart", dependencies=[Depends(require_api_key)])
async def restart_proc(name: str, supervisor: Supervisor = Depends(dep_supervisor)):
    try:
        await supervisor.restart_process(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"unknown process: {name}")
    return {"ok": True, "name": name}


@router.delete("/procs/{name}", dependencies=[Depends(require_api_key)])
async def stop_proc(name: str, disable_restart: bool = True, supervisor: Supervisor = Depends(dep_supervisor)):
    await supervisor.stop_process(name, disable_restart=disable_restart)
    return {"ok": True, "name": name, "disable_restart": disable_restart}
