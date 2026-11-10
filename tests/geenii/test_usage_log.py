import json

import pytest

from geenii import ai
from geenii.datamodels import ChatCompletionRequest


@pytest.fixture
def cache_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(ai, "GEENII_CACHE_DIR", str(tmp_path))
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


# -- text completions (generate_completion) -------------------------------------


def test_text_completion_is_logged(cache_dir):
    response = ai.generate_completion(model="fake:test", prompt="hi", source="cli", task="completion")

    assert response.usage.total_tokens == 30
    [line] = _usage_lines(cache_dir)
    assert line["provider"] == "fake"
    assert line["model"] == "test"
    assert line["context_id"] is None
    assert line["source"] == "cli"
    assert line["task"] == "completion"
    assert line["usage"]["total_tokens"] == 30
    assert line["error"] is None


def test_failed_text_completion_is_logged_and_returned(cache_dir, monkeypatch):
    from geenii.datamodels import CompletionErrorResponse
    from geenii.provider.fake.provider import FakeProvider

    def boom(self, prompt, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(FakeProvider, "generate_completion", boom)
    response = ai.generate_completion(model="fake:test", prompt="hi", task="completion")

    assert isinstance(response, CompletionErrorResponse)  # still returned, not raised
    assert response.error == "provider down"
    [line] = _usage_lines(cache_dir)
    assert line["usage"] == {}
    assert line["error"] == "RuntimeError: provider down"


def test_usage_log_write_failure_does_not_fail_the_call(cache_dir, monkeypatch):
    def broken_append(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(ai, "append_jsonl", broken_append)
    response = ai.generate_completion(model="fake:test", prompt="hi")
    assert response.output_text
    chat = ai.generate_chat_completion(ChatCompletionRequest(model="fake:test", prompt="hi"))
    assert chat.output


# -- Usage model -----------------------------------------------------------------


def test_usage_total_defaults_to_input_plus_output():
    from geenii.datamodels import Usage

    assert Usage(input_tokens=3, output_tokens=4).total_tokens == 7
    assert Usage(input_tokens=3, output_tokens=4, total_tokens=9).total_tokens == 9  # provider's own total wins
    assert Usage().total_tokens == 0


def test_usage_log_omits_unset_fields(cache_dir):
    """The log keeps its per-provider keys: only the fields a provider sets are written."""
    from geenii.datamodels import Usage

    ai._ai_usage_log("fake", "test", "ctx", Usage(input_tokens=1, output_tokens=2))
    ai._ai_usage_log(
        "fake",
        "test",
        "ctx",
        Usage(input_tokens=1, output_tokens=2, cache_read_input_tokens=5),
    )
    ai._ai_usage_log("fake", "test", "ctx", None, error="RuntimeError: boom")

    plain, cached, failed = (line["usage"] for line in _usage_lines(cache_dir))
    assert plain == {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3}
    assert cached == {
        "input_tokens": 1,
        "output_tokens": 2,
        "total_tokens": 3,
        "cache_read_input_tokens": 5,
    }
    assert failed == {}


def test_usage_reads_old_log_lines():
    """Old lines (and lines with unknown keys) still parse."""
    from geenii.datamodels import Usage

    old_ollama = {
        "input_tokens": 31,
        "output_tokens": 3,
        "total_tokens": 34,
        "load_duration": 1547,
        "future_key": 1,
    }
    usage = Usage.model_validate(old_ollama)
    assert usage.total_tokens == 34
    assert usage.load_duration == 1547
    assert "future_key" not in usage.model_dump()


# -- cache token normalisation (usage_version 2) -----------------------------------


def test_anthropic_input_includes_cache_tokens():
    from types import SimpleNamespace

    from geenii.provider.anthropic.provider import _usage_from_result

    result = SimpleNamespace(
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=50,
            cache_creation_input_tokens=300,
            cache_read_input_tokens=600,
        )
    )
    usage = _usage_from_result(result)
    assert usage.input_tokens == 1000  # 100 uncached + 300 written + 600 read
    assert usage.total_tokens == 1050
    assert usage.cache_read_input_tokens == 600
    assert usage.cache_creation_input_tokens == 300
    assert usage.uncached_input_tokens == 100


def test_anthropic_without_cache_fields():
    from types import SimpleNamespace

    from geenii.provider.anthropic.provider import _usage_from_result

    usage = _usage_from_result(SimpleNamespace(usage=SimpleNamespace(input_tokens=10, output_tokens=5)))
    assert (usage.input_tokens, usage.total_tokens) == (10, 15)
    assert usage.cache_read_input_tokens == 0


def test_openai_records_cached_tokens():
    from types import SimpleNamespace

    from geenii.provider.openai.provider import _usage_from_result

    result = SimpleNamespace(
        usage=SimpleNamespace(
            input_tokens=1000,
            output_tokens=50,
            total_tokens=1050,
            input_tokens_details=SimpleNamespace(cached_tokens=600),
        )
    )
    usage = _usage_from_result(result)
    assert usage.input_tokens == 1000  # already includes the cached part
    assert usage.cache_read_input_tokens == 600
    assert usage.cache_creation_input_tokens is None  # not reported by OpenAI
    assert usage.uncached_input_tokens == 400

    no_details = _usage_from_result(
        SimpleNamespace(usage=SimpleNamespace(input_tokens=10, output_tokens=5, total_tokens=15))
    )
    assert no_details.cache_read_input_tokens is None
    assert _usage_from_result(SimpleNamespace(usage=None)) is None


def test_usage_line_has_version(cache_dir):
    from geenii.datamodels import USAGE_VERSION

    ai.generate_chat_completion(ChatCompletionRequest(model="fake:test", prompt="hi"))
    [line] = _usage_lines(cache_dir)
    assert line["usage_version"] == USAGE_VERSION == 2


def test_from_log_entry_converts_version_1_anthropic_lines():
    from geenii.datamodels import Usage

    v1 = {
        "provider": "anthropic",
        "usage": {
            "input_tokens": 100,
            "output_tokens": 50,
            "total_tokens": 150,
            "cache_creation_input_tokens": 300,
            "cache_read_input_tokens": 600,
        },
    }
    usage = Usage.from_log_entry(v1)
    assert (usage.input_tokens, usage.total_tokens) == (1000, 1050)
    assert usage.uncached_input_tokens == 100

    # already normalised: unchanged
    v2 = {
        **v1,
        "usage": {**v1["usage"], "input_tokens": 1000, "total_tokens": 1050},
        "usage_version": 2,
    }
    assert Usage.from_log_entry(v2).input_tokens == 1000

    # other providers already counted cached input in input_tokens
    openai_v1 = {
        "provider": "openai",
        "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    }
    assert Usage.from_log_entry(openai_v1).input_tokens == 10

    assert Usage.from_log_entry({"provider": "anthropic", "usage": {}}).total_tokens == 0
