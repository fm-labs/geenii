"""
Process event log: one append-only record of process runs and of control actions
for the process manager, the scheduler and the supervisor.

Events are JSON lines in `{CACHE_DIR}/logs/proc-events-YYYY-MM.log` (UTC month), like
the AI usage log. Every line has the same envelope:

    ts          UTC timestamp with offset
    component   "pm" | "scheduler" | "supervisor"
    event       see below
    name        scheduled task / service name (null for a plain pm process)
    run_id      process manager ID or scheduler run ID
    system_pid  OS pid
    trigger     why it ran: "schedule" | "manual" | "start" | "restart"
    actor       who asked: "cli" | "api" | "daemon" ...
    cmd         the command, with secrets masked and shortened
    state, exit_code, duration_ms, error   on end events

Run events (feed proc_stats): start, exit, spawn_error, timeout, skipped, restart_scheduled, gave_up.
Audit events (control actions): service.*, task.*, config.reload, pm.kill, pm.cleanup, pm.gc.

Environment variable values are never written. Writing never raises.
"""

from __future__ import annotations

import csv
import glob
import io
import json
import logging
import os
import re
import threading
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from typing import Any, Literal

from geenii.config import GEENII_CACHE_DIR

logger = logging.getLogger(__name__)

Component = Literal["pm", "scheduler", "supervisor"]

FILE_PREFIX = "proc-events-"
# Monthly files older than this many months are deleted by prune()
KEEP_MONTHS = int(os.environ.get("GEENII_PROC_EVENTS_KEEP_MONTHS", "12"))

# Masking and shortening of commands
MAX_CMD_ARGS = 32
MAX_ARG_LEN = 200
MASK = "***"
_SECRET_WORDS = r"(?:token|secret|passw(?:or)?d|api[_-]?key|access[_-]?key|private[_-]?key|auth|credential)"
# KEY=value / --key=value with a secret-looking key
_SECRET_ASSIGN_RE = re.compile(rf"(?i)([\w.-]*{_SECRET_WORDS}[\w.-]*=)\S+")
# A flag whose next argument is a secret: --token VALUE, -p VALUE is not caught (too generic)
_SECRET_FLAG_RE = re.compile(rf"(?i)^--?[\w.-]*{_SECRET_WORDS}[\w.-]*$")
# "Bearer abc..." in shell strings / single arguments
_BEARER_RE = re.compile(r"(?i)(bearer\s+)\S+")

# Columns of the CSV export; fields not listed here go into `details` as JSON
CSV_COLUMNS = (
    "ts",
    "component",
    "event",
    "name",
    "run_id",
    "system_pid",
    "trigger",
    "actor",
    "state",
    "exit_code",
    "duration_ms",
    "error",
    "cmd",
    "details",
)

_write_lock = threading.Lock()


def log_dir() -> str:
    # Resolved at call time, so tests can redirect GEENII_CACHE_DIR
    return os.path.join(GEENII_CACHE_DIR, "logs")


def _mask_text(text: str) -> str:
    return _BEARER_RE.sub(rf"\1{MASK}", _SECRET_ASSIGN_RE.sub(rf"\1{MASK}", text))


def _shorten(text: str) -> str:
    return text if len(text) <= MAX_ARG_LEN else text[: MAX_ARG_LEN - 1] + "…"


def redact_cmd(cmd: str | list[str] | None) -> str | list[str] | None:
    """The command with secret-looking values masked, long arguments shortened and at most MAX_CMD_ARGS args."""
    if cmd is None:
        return None
    if isinstance(cmd, str):
        return _shorten(_mask_text(cmd))
    out: list[str] = []
    mask_next = False
    for arg in cmd[:MAX_CMD_ARGS]:
        arg = str(arg)
        if mask_next:
            out.append(MASK)
            mask_next = False
            continue
        if _SECRET_FLAG_RE.match(arg):
            mask_next = True
            out.append(arg)
            continue
        out.append(_shorten(_mask_text(arg)))
    if len(cmd) > MAX_CMD_ARGS:
        out.append(f"… (+{len(cmd) - MAX_CMD_ARGS} args)")
    return out


def record(component: Component, event: str, **fields: Any) -> None:
    """Append one event. Fields that are None are left out. Never raises."""
    try:
        now = datetime.now(UTC)
        entry: dict[str, Any] = {"ts": now.isoformat(timespec="milliseconds"), "component": component, "event": event}
        for key, value in fields.items():
            if value is None:
                continue
            entry[key] = redact_cmd(value) if key == "cmd" else value
        line = json.dumps(entry, separators=(",", ":"), default=str) + "\n"
        directory = log_dir()
        path = os.path.join(directory, f"{FILE_PREFIX}{now:%Y-%m}.log")
        with _write_lock:
            os.makedirs(directory, exist_ok=True)
            # One write() of a short line in append mode: lines of concurrent writers do not interleave
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
    except Exception as exc:
        logger.warning(f"Could not record process event {component}/{event}: {exc}")


def log_files(directory: str | None = None) -> list[str]:
    """The monthly event log files, oldest first."""
    return sorted(glob.glob(os.path.join(directory or log_dir(), f"{FILE_PREFIX}*.log")))


def _parse(line: str) -> dict | None:
    try:
        entry = json.loads(line)
    except ValueError:
        return None
    return entry if isinstance(entry, dict) and "ts" in entry and "event" in entry else None


def read_events(
    *,
    start: datetime | None = None,
    end: datetime | None = None,
    directory: str | None = None,
) -> Iterator[dict]:
    """Events between `start` and `end` (inclusive, aware datetimes), oldest first. Unparsable lines are skipped."""
    for path in log_files(directory):
        month = os.path.basename(path)[len(FILE_PREFIX) : -len(".log")]
        # Skip whole files outside the range (file month is the UTC month of its lines)
        if start and month < start.astimezone(UTC).strftime("%Y-%m"):
            continue
        if end and month > end.astimezone(UTC).strftime("%Y-%m"):
            continue
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    entry = _parse(line)
                    if entry is None:
                        continue
                    if start or end:
                        try:
                            ts = datetime.fromisoformat(entry["ts"])
                        except TypeError, ValueError:
                            continue
                        if (start and ts < start) or (end and ts > end):
                            continue
                    yield entry
        except OSError as exc:
            logger.warning(f"Could not read process event log {path}: {exc}")


def recent_events(
    limit: int = 200,
    *,
    component: str | None = None,
    name: str | None = None,
    event: str | None = None,
    audit: bool | None = None,
    directory: str | None = None,
) -> list[dict]:
    """The newest `limit` matching events, newest first, from the newest files backwards.

    `event` matches an exact event or a prefix ending in "." (e.g. "service.").
    `audit` True keeps only control actions (dotted event names), False only run events.
    """

    def matches(e: dict) -> bool:
        if component and e.get("component") != component:
            return False
        if name and e.get("name") != name:
            return False
        ev = e.get("event", "")
        if event and not (ev == event or (event.endswith(".") and ev.startswith(event))):
            return False
        if audit is not None and ("." in ev) != audit:
            return False
        return True

    result: list[dict] = []
    for path in reversed(log_files(directory)):
        try:
            with open(path, encoding="utf-8") as f:
                lines = f.readlines()
        except OSError as exc:
            logger.warning(f"Could not read process event log {path}: {exc}")
            continue
        for line in reversed(lines):
            entry = _parse(line)
            if entry is not None and matches(entry):
                result.append(entry)
                if len(result) >= limit:
                    return result
    return result


def to_csv_rows(events: Iterable[dict]) -> Iterator[str]:
    """CSV text (header first, then one chunk per event) with CSV_COLUMNS; other fields go into `details`."""
    buf = io.StringIO()
    writer = csv.writer(buf)

    def flush() -> str:
        text = buf.getvalue()
        buf.seek(0)
        buf.truncate()
        return text

    writer.writerow(CSV_COLUMNS)
    yield flush()
    known = set(CSV_COLUMNS)
    for e in events:
        cmd = e.get("cmd")
        details = {k: v for k, v in e.items() if k not in known}
        row = [e.get(c) for c in CSV_COLUMNS[:-2]]
        row.append(" ".join(cmd) if isinstance(cmd, list) else cmd)
        row.append(json.dumps(details, separators=(",", ":")) if details else "")
        writer.writerow(["" if v is None else v for v in row])
        yield flush()


def prune(keep_months: int = KEEP_MONTHS, directory: str | None = None) -> list[str]:
    """Delete monthly files older than `keep_months` months (0 keeps everything). Returns the deleted paths."""
    if keep_months <= 0:
        return []
    now = datetime.now(UTC)
    index = now.year * 12 + now.month - 1 - (keep_months - 1)
    oldest_kept = f"{index // 12:04d}-{index % 12 + 1:02d}"
    removed = []
    for path in log_files(directory):
        month = os.path.basename(path)[len(FILE_PREFIX) : -len(".log")]
        if month < oldest_kept:
            try:
                os.remove(path)
                removed.append(path)
            except OSError as exc:
                logger.warning(f"Could not delete old process event log {path}: {exc}")
    if removed:
        logger.info(f"Deleted {len(removed)} process event log(s) older than {keep_months} months")
    return removed
