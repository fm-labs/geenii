"""
AI usage statistics, calculated from the usage log (`{CACHE_DIR}/logs/ai-usage-YYYY-MM.log`, see ai._ai_usage_log).

Each log file is aggregated into per-day buckets once and cached, in memory and as JSON in `{CACHE_DIR}/stats/`,
keyed by the file's size and mtime. Past months never change, so only the current month's file is read again,
and only after new lines were appended. `usage_stats()` then merges the cached days of the requested range.

Days are local server days: timestamps with an offset are converted to local time, and older lines without one
were written in local time already.
"""

from __future__ import annotations

import glob
import json
import logging
import os
import tempfile
import threading
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

import pydantic

from geenii.config import GEENII_CACHE_DIR
from geenii.datamodels import Usage

logger = logging.getLogger(__name__)

# bump when the cached aggregate format changes, so old cache files are recalculated
CACHE_VERSION = 1

# counters summed per (provider, model, source, task) and day
TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cache_read_input_tokens",
    "cache_creation_input_tokens",
)
COUNTER_FIELDS = ("calls", "failed", *TOKEN_FIELDS, "duration_ms", "timed_calls")

# dimensions a breakdown can be grouped by
DIMENSIONS = ("provider", "model", "source", "task")

# a day: {"rows": {row key: Counter}, "hours": [calls per local hour]}
DayAggregate = dict


def _log_dir() -> str:
    return os.path.join(GEENII_CACHE_DIR, "logs")


def _cache_dir() -> str:
    return os.path.join(GEENII_CACHE_DIR, "stats")


def _row_key(entry: dict) -> str:
    # lines written before source/task were logged have neither
    return json.dumps(
        [
            entry.get("provider") or "unknown",
            entry.get("model") or "unknown",
            entry.get("source") or "untagged",
            entry.get("task") or "untagged",
        ]
    )


def _local_time(timestamp: str) -> datetime | None:
    try:
        ts = datetime.fromisoformat(timestamp)
    except TypeError, ValueError:
        return None
    return ts.astimezone() if ts.tzinfo else ts


def _entry_counters(entry: dict) -> Counter:
    counters = Counter(calls=1, failed=1 if entry.get("error") else 0)
    try:
        usage = Usage.from_log_entry(entry)  # converts older log conventions
    except pydantic.ValidationError:
        return counters  # malformed usage: count the call, without tokens
    for field in TOKEN_FIELDS:
        counters[field] += getattr(usage, field) or 0
    if usage.total_duration:  # only ollama reports timings
        counters["duration_ms"] += usage.total_duration
        counters["timed_calls"] += 1
    return counters


def aggregate_log_file(path: str) -> dict[str, DayAggregate]:
    """Per-day aggregates of one usage log file. Unparsable lines are skipped."""
    days: dict[str, DayAggregate] = {}
    with open(path, "r") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if not isinstance(entry, dict):
                continue
            ts = _local_time(entry.get("timestamp"))
            if ts is None:
                continue
            day = days.setdefault(ts.date().isoformat(), {"rows": {}, "hours": [0] * 24})
            day["rows"].setdefault(_row_key(entry), Counter()).update(_entry_counters(entry))
            day["hours"][ts.hour] += 1
    return days


class UsageStatsCache:
    """Per-file day aggregates, invalidated by a change of the file's size or mtime."""

    def __init__(self, log_dir: str | None = None, cache_dir: str | None = None):
        self._log_dir = log_dir
        self._cache_dir = cache_dir
        self._files: dict[str, tuple[tuple[int, int], dict[str, DayAggregate]]] = {}
        self._lock = threading.Lock()

    @property
    def log_dir(self) -> str:
        return self._log_dir or _log_dir()

    @property
    def cache_dir(self) -> str:
        return self._cache_dir or _cache_dir()

    def _cache_file(self, path: str) -> str:
        return os.path.join(self.cache_dir, Path(path).stem + ".json")

    def _read_cache_file(self, path: str, signature: tuple[int, int]) -> dict[str, DayAggregate] | None:
        try:
            with open(self._cache_file(path), "r") as f:
                data = json.load(f)
        except OSError, ValueError:
            return None
        if data.get("version") != CACHE_VERSION or tuple(data.get("signature") or ()) != signature:
            return None
        return {
            day: {
                "rows": {k: Counter(v) for k, v in agg["rows"].items()},
                "hours": agg["hours"],
            }
            for day, agg in data["days"].items()
        }

    def _write_cache_file(self, path: str, signature: tuple[int, int], days: dict[str, DayAggregate]) -> None:
        """Atomic write; a failure only costs a recalculation after a restart."""
        target = self._cache_file(path)
        try:
            os.makedirs(self.cache_dir, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.cache_dir, suffix=".tmp")
            with os.fdopen(fd, "w") as f:
                json.dump(
                    {
                        "version": CACHE_VERSION,
                        "signature": list(signature),
                        "days": days,
                    },
                    f,
                )
            os.replace(tmp, target)
        except OSError as e:
            logger.warning(f"Could not write usage stats cache {target}: {e}")

    def _file_days(self, path: str, refresh: bool) -> dict[str, DayAggregate]:
        stat = os.stat(path)
        signature = (stat.st_size, stat.st_mtime_ns)
        cached = self._files.get(path)
        if cached and cached[0] == signature and not refresh:
            return cached[1]
        days = None if refresh else self._read_cache_file(path, signature)
        if days is None:
            days = aggregate_log_file(path)
            self._write_cache_file(path, signature, days)
        self._files[path] = (signature, days)
        return days

    def days(self, refresh: bool = False) -> dict[str, DayAggregate]:
        """Aggregates of all days in all usage log files. A day can span two files (around a month boundary)."""
        merged: dict[str, DayAggregate] = {}
        with self._lock:
            paths = sorted(glob.glob(os.path.join(self.log_dir, "ai-usage-*.log")))
            for path in set(self._files) - set(paths):
                del self._files[path]
            for path in paths:
                try:
                    file_days = self._file_days(path, refresh)
                except OSError as e:
                    logger.warning(f"Could not read usage log {path}: {e}")
                    continue
                for day, agg in file_days.items():
                    target = merged.setdefault(day, {"rows": {}, "hours": [0] * 24})
                    for key, counters in agg["rows"].items():
                        target["rows"].setdefault(key, Counter()).update(counters)
                    target["hours"] = [a + b for a, b in zip(target["hours"], agg["hours"])]
        return merged


_default_cache = UsageStatsCache()


def _totals(counters: Counter) -> dict:
    result = {field: counters.get(field, 0) for field in COUNTER_FIELDS}
    result["avg_duration_ms"] = round(result["duration_ms"] / result["timed_calls"]) if result["timed_calls"] else None
    return result


def usage_stats(
    start: date | None = None,
    end: date | None = None,
    *,
    refresh: bool = False,
    cache: UsageStatsCache | None = None,
) -> dict:
    """
    Usage between `start` and `end` (inclusive, local days). `end` defaults to today and `start` to the first
    day with usage. The daily series has an entry for every day of the range, with zeros for days without calls.
    """
    days = (cache or _default_cache).days(refresh=refresh)
    available = sorted(days)
    end = end or date.today()
    if start is None:
        start = date.fromisoformat(available[0]) if available else end
    if start > end:
        raise ValueError("start must not be after end")

    total = Counter()
    hours = [0] * 24
    breakdowns: dict[str, dict[str, Counter]] = {d: {} for d in (*DIMENSIONS, "model_id")}
    daily = []
    day = start
    while day <= end:
        agg = days.get(day.isoformat())
        day_total = Counter()
        by_provider = Counter()
        if agg:
            for key, counters in agg["rows"].items():
                provider, model, source, task = json.loads(key)
                day_total.update(counters)
                by_provider[provider] += counters.get("total_tokens", 0)
                for dimension, value in (
                    ("provider", provider),
                    ("model", model),
                    ("source", source),
                    ("task", task),
                    ("model_id", f"{provider}:{model}"),
                ):
                    breakdowns[dimension].setdefault(value, Counter()).update(counters)
            hours = [a + b for a, b in zip(hours, agg["hours"])]
        total.update(day_total)
        daily.append(
            {
                "date": day.isoformat(),
                **_totals(day_total),
                "tokens_by_provider": dict(by_provider),
            }
        )
        day += timedelta(days=1)

    def breakdown(dimension: str) -> list[dict]:
        rows = [{"key": key, **_totals(counters)} for key, counters in breakdowns[dimension].items()]
        return sorted(rows, key=lambda r: (-r["total_tokens"], -r["calls"], r["key"]))

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "first_day": available[0] if available else None,
        "last_day": available[-1] if available else None,
        "totals": _totals(total),
        "active_days": sum(1 for d in daily if d["calls"]),
        "daily": daily,
        "hourly": hours,
        "by_provider": breakdown("provider"),
        "by_model": breakdown("model_id"),
        "by_source": breakdown("source"),
        "by_task": breakdown("task"),
    }
