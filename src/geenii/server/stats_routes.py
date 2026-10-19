from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query

from geenii.datamodels import Problem
from geenii.usage_stats import usage_stats

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/usage", responses={400: {"model": Problem, "description": "Invalid date range"}})
def get_usage_stats(days: int | None = Query(30, ge=0, le=3660, description="Last n days up to `end`; 0 for all days with usage"),
                    start: date | None = Query(None, description="First day (inclusive); overrides `days`"),
                    end: date | None = Query(None, description="Last day (inclusive), defaults to today"),
                    refresh: bool = Query(False, description="Recalculate instead of using the cached aggregates")) -> dict:
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
