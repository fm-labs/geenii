import json

import pytest

from geenii import ai
from geenii.datamodels import ChatCompletionRequest


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(ai, "CACHE_DIR", str(tmp_path))
    return tmp_path


def _usage_lines(cache_dir) -> list[dict]:
    lines = []
    for path in sorted((cache_dir / "logs").glob("ai-usage-*.log")):
        lines += [json.loads(line) for line in path.read_text().splitlines()]
    return lines


def test_usage_line_has_source_and_task(cache_dir):
    request = ChatCompletionRequest(model="fake:test", prompt="hi", context_id="ctx")
    ai.generate_chat_completion(request, source="agent:tester", task="llm")

    [line] = _usage_lines(cache_dir)
    assert line["provider"] == "fake"
    assert line["model"] == "test"
    assert line["context_id"] == "ctx"
    assert line["source"] == "agent:tester"
    assert line["task"] == "llm"
    assert line["usage"]["total_tokens"] == 30


def test_timestamp_is_utc_with_offset_and_matches_the_file(cache_dir):
    from datetime import datetime, timedelta

    ai.generate_chat_completion(ChatCompletionRequest(model="fake:test", prompt="hi"))

    [path] = (cache_dir / "logs").glob("ai-usage-*.log")
    [line] = _usage_lines(cache_dir)
    timestamp = datetime.fromisoformat(line["timestamp"])
    assert line["timestamp"].endswith("+00:00")
    assert timestamp.utcoffset() == timedelta(0)
    assert path.name == f"ai-usage-{timestamp.strftime('%Y-%m')}.log"


def test_untagged_call_logs_nulls(cache_dir):
    ai.generate_chat_completion(ChatCompletionRequest(model="fake:test", prompt="hi"))

    [line] = _usage_lines(cache_dir)
    assert line["source"] is None
    assert line["task"] is None
    assert line["error"] is None
    assert line["context_id"]  # generated


def test_failed_call_is_logged_and_reraised(cache_dir, monkeypatch):
    from geenii.provider.fake.provider import FakeProvider

    def boom(self, request, tool_registry=None):
        raise RuntimeError("provider down\nretry later")

    monkeypatch.setattr(FakeProvider, "generate_chat_completion", boom)
    request = ChatCompletionRequest(model="fake:test", prompt="hi", context_id="ctx")
    with pytest.raises(RuntimeError, match="provider down"):
        ai.generate_chat_completion(request, source="agent:tester", task="llm")

    [line] = _usage_lines(cache_dir)
    assert line["provider"] == "fake"
    assert line["model"] == "test"
    assert line["context_id"] == "ctx"
    assert line["source"] == "agent:tester"
    assert line["task"] == "llm"
    assert line["usage"] == {}
    assert line["error"] == "RuntimeError: provider down retry later"  # one line


def test_invalid_model_id_is_logged_without_provider(cache_dir):
    with pytest.raises(ValueError):
        ai.generate_chat_completion(ChatCompletionRequest(model="no-prefix", prompt="hi"), task="llm")

    [line] = _usage_lines(cache_dir)
    assert line["provider"] is None
    assert line["model"] == "no-prefix"
    assert line["context_id"]
    assert line["error"].startswith("ValueError: Invalid model ID format")


def test_long_errors_are_truncated():
    text = ai._error_text(RuntimeError("x" * 2000))
    assert len(text) == ai._MAX_ERROR_LENGTH
    assert text.endswith("…")


def test_logging_failure_does_not_hide_the_error(cache_dir, monkeypatch):
    def broken_log(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(ai, "_ai_usage_log", broken_log)
    with pytest.raises(ValueError, match="Invalid model ID"):
        ai.generate_chat_completion(ChatCompletionRequest(model="no-prefix", prompt="hi"))
