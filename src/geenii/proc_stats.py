"""
Process statistics, calculated from the process event log (see proc_events).

Counts per local day and per (component, name): finished runs by state, timeouts,
skipped runs, scheduled restarts, spawn errors, run time and control actions.
Each monthly log file is aggregated once and cached like the AI usage stats
(usage_stats.UsageStatsCache), so only the current month's file is read again.
"""

from __future__ import annotations

import json
import os
import threading
from collections import Counter
from datetime import date, timedelta

from geenii import proc_events
from geenii.usage_stats import DayAggregate, UsageStatsCache, _local_time

# bump when the cached aggregate format changes, so old cache files are recalculated
CACHE_VERSION = 2

COUNTER_FIELDS = (
    "runs",  # finished runs (exit events)
    "completed",
    "failed",
    "killed",
    "timeouts",
    "skipped",
    "restarts",
    "spawn_errors",
    "gave_up",  # services the supervisor stopped restarting after max_failures
    "duration_ms",  # summed over finished runs with a duration
    "timed_runs",
    "actions",  # control actions (audit events)
)

# Name used for processes started without a task or service name (plain pm processes)
ADHOC_NAME = "(ad hoc)"

_STATE_COUNTERS = {"completed": "completed", "failed": "failed", "killed": "killed"}
_EVENT_COUNTERS = {
    "timeout": "timeouts",
    "skipped": "skipped",
    "restart_scheduled": "restarts",
    "spawn_error": "spawn_errors",
    "gave_up": "gave_up",
}


def _row_key(entry: dict) -> str:
    return json.dumps([entry.get("component") or "pm", entry.get("name") or ADHOC_NAME])


def _entry_counters(entry: dict) -> Counter:
    event = entry.get("event") or ""
    counters = Counter()
    if event == "exit":
        counters["runs"] += 1
        state = _STATE_COUNTERS.get(entry.get("state") or "")
        if state:
            counters[state] += 1
        duration = entry.get("duration_ms")
        if isinstance(duration, (int, float)) and duration >= 0:
            counters["duration_ms"] += int(duration)
            counters["timed_runs"] += 1
    elif event in _EVENT_COUNTERS:
        counters[_EVENT_COUNTERS[event]] += 1
    elif "." in event:
        counters["actions"] += 1
    return counters


def aggregate_event_file(path: str) -> dict[str, DayAggregate]:
    """Per-day aggregates of one event log file; `hours` counts started runs. Unparsable lines are skipped."""
    days: dict[str, DayAggregate] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            ts = _local_time(entry.get("ts"))
            if ts is None:
                continue
            day = days.setdefault(ts.date().isoformat(), {"rows": {}, "hours": [0] * 24})
            counters = _entry_counters(entry)
            if counters:
                day["rows"].setdefault(_row_key(entry), Counter()).update(counters)
            if entry.get("event") == "start":
                day["hours"][ts.hour] += 1
    return days


_caches: dict[str, UsageStatsCache] = {}
_caches_lock = threading.Lock()


def _cache() -> UsageStatsCache:
    """One cache per log directory (resolved at call time, so tests can redirect it)."""
    log_dir = proc_events.log_dir()
    with _caches_lock:
        cache = _caches.get(log_dir)
        if cache is None:
            cache = UsageStatsCache(
                log_dir,
                os.path.join(os.path.dirname(log_dir), "stats"),
                pattern=f"{proc_events.FILE_PREFIX}*.log",
                aggregate=aggregate_event_file,
                version=CACHE_VERSION,
            )
            _caches[log_dir] = cache
        return cache


def _totals(counters: Counter) -> dict:
    result = {field: counters.get(field, 0) for field in COUNTER_FIELDS}
    result["avg_duration_ms"] = round(result["duration_ms"] / result["timed_runs"]) if result["timed_runs"] else None
    return result


def _sort_key(row: dict) -> tuple:
    return (-row["runs"], -row["failed"], -row["actions"], row["key"])


def proc_stats(
    start: date | None = None,
    end: date | None = None,
    *,
    refresh: bool = False,
    cache: UsageStatsCache | None = None,
) -> dict:
    """
    Process stats between `start` and `end` (inclusive, local days). `end` defaults to today and `start`
    to the first day with events. The daily series has an entry for every day of the range.
    """
    days = (cache or _cache()).days(refresh=refresh)
    available = sorted(days)
    end = end or date.today()
    if start is None:
        start = date.fromisoformat(available[0]) if available else end
    if start > end:
        raise ValueError("start must not be after end")

    total = Counter()
    hours = [0] * 24
    by_component: dict[str, Counter] = {}
    by_name: dict[tuple[str, str], Counter] = {}
    daily = []
    day = start
    while day <= end:
        agg = days.get(day.isoformat())
        day_total = Counter()
        if agg:
            for key, counters in agg["rows"].items():
                component, name = json.loads(key)
                day_total.update(counters)
                by_component.setdefault(component, Counter()).update(counters)
                by_name.setdefault((component, name), Counter()).update(counters)
            hours = [a + b for a, b in zip(hours, agg["hours"])]
        total.update(day_total)
        daily.append({"date": day.isoformat(), **_totals(day_total)})
        day += timedelta(days=1)

    components = sorted(
        ({"key": c, **_totals(counters)} for c, counters in by_component.items()),
        key=_sort_key,
    )
    names = sorted(
        ({"key": f"{c}:{n}", "component": c, "name": n, **_totals(counters)} for (c, n), counters in by_name.items()),
        key=_sort_key,
    )
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "first_day": available[0] if available else None,
        "last_day": available[-1] if available else None,
        "totals": _totals(total),
        "active_days": sum(1 for d in daily if d["runs"] or d["actions"]),
        "daily": daily,
        "hourly": hours,
        "by_component": components,
        "by_name": names,
    }
