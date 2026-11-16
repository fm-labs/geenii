from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from geenii import proc_events
from geenii.datamodels import Problem
from geenii.proc_stats import proc_stats
from geenii.usage_stats import usage_stats

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/usage", responses={400: {"model": Problem, "description": "Invalid date range"}})
def get_usage_stats(
    days: int | None = Query(
        30,
        ge=0,
        le=3660,
        description="Last n days up to `end`; 0 for all days with usage",
    ),
    start: date | None = Query(None, description="First day (inclusive); overrides `days`"),
    end: date | None = Query(None, description="Last day (inclusive), defaults to today"),
    refresh: bool = Query(False, description="Recalculate instead of using the cached aggregates"),
) -> dict:
    """
    AI usage statistics from the usage log: totals, a daily series, calls per hour of day,
    and breakdowns by provider, model, source and task. Days are local server days.
    """
    end = end or date.today()
    if start is None and days:
        start = end - timedelta(days=days - 1)
    try:
        return usage_stats(start, end, refresh=refresh)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _date_range(days: int | None, start: date | None, end: date | None) -> tuple[date | None, date]:
    end = end or date.today()
    if start is None and days:
        start = end - timedelta(days=days - 1)
    return start, end


@router.get("/processes", responses={400: {"model": Problem, "description": "Invalid date range"}})
def get_process_stats(
    days: int | None = Query(30, ge=0, le=3660, description="Last n days up to `end`; 0 for all days with events"),
    start: date | None = Query(None, description="First day (inclusive); overrides `days`"),
    end: date | None = Query(None, description="Last day (inclusive), defaults to today"),
    refresh: bool = Query(False, description="Recalculate instead of using the cached aggregates"),
) -> dict:
    """
    Process statistics from the process event log (process manager, scheduler, supervisor):
    totals, a daily series, runs started per hour of day, and breakdowns by component and
    by task/service name. Days are local server days.
    """
    start, end = _date_range(days, start, end)
    try:
        return proc_stats(start, end, refresh=refresh)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/processes/events")
def get_process_events(
    limit: int = Query(200, ge=1, le=5000),
    component: str | None = Query(None, description="pm, scheduler or supervisor"),
    name: str | None = Query(None, description="Task or service name"),
    event: str | None = Query(None, description="Exact event, or a prefix ending in '.' (e.g. 'service.')"),
    audit: bool | None = Query(None, description="true: control actions only; false: run events only"),
) -> dict:
    """The newest process events (runs and control actions), newest first."""
    return {
        "events": proc_events.recent_events(limit, component=component, name=name, event=event, audit=audit),
    }


@router.get("/processes/events.csv", responses={400: {"model": Problem, "description": "Invalid date range"}})
def export_process_events(
    days: int | None = Query(30, ge=0, le=3660, description="Last n days up to `end`; 0 for all events"),
    start: date | None = Query(None, description="First day (inclusive); overrides `days`"),
    end: date | None = Query(None, description="Last day (inclusive), defaults to today"),
) -> StreamingResponse:
    """The process events of a date range (local days) as CSV, oldest first. Extra fields are in `details` (JSON)."""
    start, end = _date_range(days, start, end)
    if start and start > end:
        raise HTTPException(status_code=400, detail="start must not be after end")
    tz = datetime.now().astimezone().tzinfo
    since = datetime.combine(start, time.min, tz) if start else None
    until = datetime.combine(end, time.max, tz)
    filename = f"process-events-{start.isoformat() if start else 'all'}-{end.isoformat()}.csv"
    return StreamingResponse(
        proc_events.to_csv_rows(proc_events.read_events(start=since, end=until)),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
