from fastapi import Depends, Request, APIRouter

from geenii.scheduler import Scheduler

router = APIRouter(prefix="/scheduler", tags=["scheduler"])


def dep_scheduler(request: Request) -> Scheduler:
    return request.app.state.scheduler

# --- Status & logs ----------------------------------------------------------

@router.get("")
async def list_tasks(scheduler: Scheduler = Depends(dep_scheduler)):
    return scheduler.status

