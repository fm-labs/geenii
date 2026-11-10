import json
import os
from datetime import date

import pytest
from fastapi.testclient import TestClient

from geenii import usage_stats
from geenii.server.server import app
from geenii.usage_stats import UsageStatsCache


def _line(timestamp, provider="ollama", model="qwen3:8b", usage=None, **extra):
    return json.dumps(
        {
            "timestamp": timestamp,
            "provider": provider,
            "context_id": "ctx",
            "model": model,
            "usage": usage if usage is not None else {"input_tokens": 10, "output_tokens": 5},
            "usage_version": 2,
            **extra,
        }
    )


@pytest.fixture
def logs(tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "ai-usage-2026-09.log").write_text(
        "\n".join(
            [
                # naive timestamps are local time already
                _line("2026-09-30T23:30:00"),
                "not json",
                _line("not a timestamp"),
            ]
        )
        + "\n"
    )
    (log_dir / "ai-usage-2026-10.log").write_text(
        "\n".join(
            [
                _line(
                    "2026-10-01T09:15:00",
                    provider="anthropic",
                    model="claude",
                    source="agent:a",
                    task="llm",
                    usage={
                        "input_tokens": 100,
                        "output_tokens": 20,
                        "cache_read_input_tokens": 40,
                    },
                ),
                _line(
                    "2026-10-01T09:45:00",
                    provider="anthropic",
                    model="claude",
                    source="agent:a",
                    task="llm",
                    usage={},
                    error="RuntimeError: down",
                ),
                _line(
                    "2026-10-03T14:00:00",
                    usage={
                        "input_tokens": 1,
                        "output_tokens": 1,
                        "total_duration": 300,
                    },
                ),
                _line("2026-10-03T15:00:00", usage={"input_tokens": "bad"}),
            ]
        )
        + "\n"
    )
    return log_dir


@pytest.fixture
def cache(logs, tmp_path):
    return UsageStatsCache(log_dir=str(logs), cache_dir=str(tmp_path / "stats"))


def test_totals_and_breakdowns(cache):
    stats = usage_stats.usage_stats(date(2026, 9, 30), date(2026, 10, 3), cache=cache)

    assert stats["first_day"] == "2026-09-30" and stats["last_day"] == "2026-10-03"
    totals = stats["totals"]
    assert totals["calls"] == 5 and totals["failed"] == 1
    assert totals["input_tokens"] == 10 + 100 + 1
    assert totals["total_tokens"] == 15 + 120 + 2
    assert totals["cache_read_input_tokens"] == 40
    # only ollama reports durations
    assert totals["timed_calls"] == 1 and totals["avg_duration_ms"] == 300
    assert stats["active_days"] == 3

    by_model = {r["key"]: r for r in stats["by_model"]}
    assert by_model["anthropic:claude"]["calls"] == 2
    assert by_model["ollama:qwen3:8b"]["calls"] == 3  # the malformed usage still counts as a call
    assert stats["by_model"][0]["key"] == "anthropic:claude"  # sorted by tokens
    assert {r["key"] for r in stats["by_source"]} == {"agent:a", "untagged"}
    assert {r["key"] for r in stats["by_task"]} == {"llm", "untagged"}
    assert stats["hourly"][9] == 2 and stats["hourly"][23] == 1 and sum(stats["hourly"]) == 5


def test_daily_series_fills_days_without_calls(cache):
    daily = usage_stats.usage_stats(date(2026, 10, 1), date(2026, 10, 4), cache=cache)["daily"]

    assert [d["date"] for d in daily] == [
        "2026-10-01",
        "2026-10-02",
        "2026-10-03",
        "2026-10-04",
    ]
    assert [d["calls"] for d in daily] == [2, 0, 2, 0]
    assert daily[0]["tokens_by_provider"] == {"anthropic": 120}


def test_start_defaults_to_first_day(cache):
    stats = usage_stats.usage_stats(end=date(2026, 10, 3), cache=cache)
    assert stats["start"] == "2026-09-30"


def test_start_after_end_is_an_error(cache):
    with pytest.raises(ValueError):
        usage_stats.usage_stats(date(2026, 10, 3), date(2026, 10, 1), cache=cache)


def test_offset_timestamps_are_converted_to_local_days(tmp_path, monkeypatch):
    monkeypatch.setenv("TZ", "America/New_York")
    import time

    time.tzset()
    try:
        log = tmp_path / "ai-usage-2026-10.log"
        log.write_text(_line("2026-10-02T02:00:00+00:00") + "\n")
        assert list(usage_stats.aggregate_log_file(str(log))) == ["2026-10-01"]
    finally:
        monkeypatch.delenv("TZ")
        time.tzset()


def test_aggregates_are_cached_until_the_file_changes(cache, logs, monkeypatch):
    calls = []
    original = usage_stats.aggregate_log_file
    monkeypatch.setattr(
        usage_stats,
        "aggregate_log_file",
        lambda path: calls.append(path) or original(path),
    )

    cache.days()
    assert len(calls) == 2
    cache.days()
    assert len(calls) == 2  # memory cache

    # a new instance reads the JSON cache files instead of the logs
    fresh = UsageStatsCache(log_dir=cache.log_dir, cache_dir=cache.cache_dir)
    assert fresh.days() == cache.days()
    assert len(calls) == 2

    october = logs / "ai-usage-2026-10.log"
    with open(october, "a") as f:
        f.write(_line("2026-10-05T10:00:00") + "\n")
    days = cache.days()
    assert calls[2:] == [str(october)]  # only the changed file is read again
    assert "2026-10-05" in days

    cache.days(refresh=True)
    assert len(calls) == 5


def test_removed_log_files_are_dropped(cache, logs):
    assert "2026-09-30" in cache.days()
    os.remove(logs / "ai-usage-2026-09.log")
    assert "2026-09-30" not in cache.days()


@pytest.fixture
def client(cache, monkeypatch):
    monkeypatch.setattr(usage_stats, "_default_cache", cache)
    return TestClient(app)


def test_route_with_explicit_range(client):
    response = client.get("/api/v1/stats/usage", params={"start": "2026-10-01", "end": "2026-10-03"})

    assert response.status_code == 200
    body = response.json()
    assert (body["start"], body["end"]) == ("2026-10-01", "2026-10-03")
    assert body["totals"]["calls"] == 4


def test_route_last_n_days(client):
    body = client.get("/api/v1/stats/usage", params={"days": 2, "end": "2026-10-03"}).json()
    assert body["start"] == "2026-10-02"
    assert len(body["daily"]) == 2


def test_route_all_days(client):
    body = client.get("/api/v1/stats/usage", params={"days": 0, "end": "2026-10-03"}).json()
    assert body["start"] == "2026-09-30"


def test_route_invalid_range_is_400(client):
    response = client.get("/api/v1/stats/usage", params={"start": "2026-10-03", "end": "2026-10-01"})
    assert response.status_code == 400
