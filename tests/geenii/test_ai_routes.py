import inspect
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from geenii.datamodels import (
    AudioTranscriptionApiResponse,
    CompletionErrorResponse,
    CompletionResponse,
)
from geenii.server import ai_routes
from geenii.server.server import app


@pytest.fixture
def sessions_dir(tmp_path, monkeypatch):
    path = tmp_path / "home" / ".geenii" / "sessions" / "chat"
    monkeypatch.setattr(ai_routes, "GEENII_CHAT_SESSIONS_DIR", path)
    return path


@pytest.fixture
def client():
    return TestClient(app)


def _chat(client, context_id=None):
    body = {"model": "fake:test", "prompt": "hi"}
    if context_id is not None:
        body["context_id"] = context_id
    return client.post("/api/v1/ai/chat/completion", json=body)


@pytest.mark.parametrize(
    "context_id",
    [
        "../../../escaped",
        "..",
        "a/b",
        "/etc",
        "x" * 65,
        "with space",
        "dot.dot",
    ],
)
def test_chat_completion_rejects_unsafe_context_id(client, sessions_dir, tmp_path, context_id):
    response = _chat(client, context_id)

    assert response.status_code == 400
    assert "context_id" in response.json()["detail"]
    # nothing was created anywhere under the temp root
    assert not any(p.name == "memory.jsonl" for p in tmp_path.rglob("*"))
    assert not (tmp_path / "escaped").exists()


def test_chat_completion_stores_memory_in_session_dir(client, sessions_dir):
    response = _chat(client, "chat-1_A")

    assert response.status_code == 200
    assert (sessions_dir / "chat-1_A" / "memory.jsonl").is_file()


def test_chat_completion_generates_context_id(client, sessions_dir):
    response = _chat(client)

    assert response.status_code == 200
    context_id = response.json()["context_id"]
    assert (sessions_dir / context_id / "memory.jsonl").is_file()


def test_ai_handlers_are_sync():
    """Blocking ai.* calls must not run on the event loop; sync handlers run in FastAPI's threadpool."""
    handlers = [route.endpoint for route in ai_routes.router.routes]
    assert handlers
    assert not [h.__name__ for h in handlers if inspect.iscoroutinefunction(h)]


# -- error handling, parameter forwarding, uploads ---------------------------


def _completion_response(text="ok"):
    return CompletionResponse(id=uuid.uuid4().hex, timestamp=int(time.time()), output=[], output_text=text)


def test_completion_forwards_model_parameters(client, monkeypatch):
    calls = []

    def fake_generate_completion(**kwargs):
        calls.append(kwargs)
        return _completion_response()

    monkeypatch.setattr(ai_routes.ai, "generate_completion", fake_generate_completion)

    response = client.post(
        "/api/v1/ai/completion",
        json={
            "model": "fake:test",
            "prompt": "hi",
            "system": ["be brief"],
            "temperature": 0.2,
            "max_tokens": 64,
            "stream": True,
        },
    )

    assert response.status_code == 200
    assert calls == [
        {
            "model": "fake:test",
            "prompt": "hi",
            "stream": False,
            "source": "api",
            "task": "completion",
            "system": ["be brief"],
            "temperature": 0.2,
            "max_tokens": 64,
        }
    ]  # unset (None) params dropped


def test_provider_error_returns_502_problem(client, monkeypatch):
    monkeypatch.setattr(
        ai_routes.ai,
        "generate_completion",
        lambda **kwargs: CompletionErrorResponse(error="provider down"),
    )

    response = client.post("/api/v1/ai/completion", json={"model": "fake:test", "prompt": "hi"})

    assert response.status_code == 502
    assert response.json() == {
        "error": "provider down",
        "status": 502,
        "detail": "provider down",
    }


def test_malformed_model_id_returns_400(client):
    response = client.post("/api/v1/ai/completion", json={"model": "no-provider-prefix", "prompt": "hi"})

    assert response.status_code == 400
    assert "provider:model" in response.json()["detail"]


def test_chat_completion_forwards_system_and_parameters(client, sessions_dir, monkeypatch):
    requests = []
    real = ai_routes.ai.generate_chat_completion

    tags = []

    def spy(request, **kwargs):
        requests.append(request)
        tags.append(kwargs)
        return real(request, **kwargs)

    monkeypatch.setattr(ai_routes.ai, "generate_chat_completion", spy)

    assert _chat(client, "c1").status_code == 200
    assert requests[-1].system == [ai_routes.DEFAULT_CHAT_SYSTEM_PROMPT]
    assert tags[-1] == {"source": "api", "task": "chat_completion"}

    response = client.post(
        "/api/v1/ai/chat/completion",
        json={
            "model": "fake:test",
            "prompt": "again",
            "context_id": "c1",
            "system": ["custom"],
            "temperature": 0.7,
        },
    )
    assert response.status_code == 200
    assert requests[-1].system == ["custom"]
    assert requests[-1].temperature == 0.7
    assert [m.role for m in requests[-1].messages] == [
        "user",
        "assistant",
    ]  # history from the first turn


def test_chat_completion_provider_error_returns_502_and_keeps_memory_clean(client, sessions_dir, monkeypatch):
    def boom(request, **kwargs):
        raise RuntimeError("provider down")

    monkeypatch.setattr(ai_routes.ai, "generate_chat_completion", boom)

    response = _chat(client, "c2")

    assert response.status_code == 502
    assert response.json()["detail"] == "provider down"
    memory_file = sessions_dir / "c2" / "memory.jsonl"
    assert not memory_file.exists() or memory_file.read_text() == ""


def test_audio_translate_returns_501(client):
    response = client.post("/api/v1/ai/audio/translate", json={"input_file": "x.wav"})

    assert response.status_code == 501
    assert response.json()["status"] == 501


def test_ai_operation_ids_are_unique():
    ids = [op["operationId"] for path, ops in app.openapi()["paths"].items() if "/ai/" in path for op in ops.values()]
    assert len(ids) == len(set(ids))
    assert any("generate_audio_translation" in i for i in ids)


@pytest.fixture
def upload_dir(tmp_path, monkeypatch):
    path = tmp_path / "uploads" / "audio"
    monkeypatch.setattr(ai_routes, "AUDIO_UPLOAD_DIR", path)
    return path


def _transcribe(client, data: bytes, content_type="audio/wav", filename="clip.wav"):
    return client.post(
        "/api/v1/ai/audio/transcribe",
        files={"input_blob": (filename, data, content_type)},
    )


def test_transcribe_deletes_upload_after_request(client, upload_dir, monkeypatch):
    seen = []

    def fake_transcription(request):
        seen.append(request.input_file)
        assert open(request.input_file, "rb").read() == b"RIFF-audio"
        return AudioTranscriptionApiResponse(id="t1", timestamp=0, output_text="hello")

    monkeypatch.setattr(ai_routes.ai, "generate_audio_transcription", fake_transcription)

    response = _transcribe(client, b"RIFF-audio", filename="../../evil.wav")

    assert response.status_code == 200
    assert response.json()["output_text"] == "hello"
    assert seen and seen[0].startswith(str(upload_dir)) and seen[0].endswith(".wav")
    assert list(upload_dir.iterdir()) == []


def test_transcribe_rejects_oversized_upload(client, upload_dir, monkeypatch):
    monkeypatch.setattr(ai_routes, "MAX_AUDIO_UPLOAD_BYTES", 10)
    monkeypatch.setattr(ai_routes, "_UPLOAD_CHUNK_SIZE", 4)
    monkeypatch.setattr(
        ai_routes.ai,
        "generate_audio_transcription",
        lambda request: pytest.fail("provider must not be called"),
    )

    response = _transcribe(client, b"x" * 11)

    assert response.status_code == 413
    assert list(upload_dir.iterdir()) == []


def test_transcribe_rejects_non_audio(client, upload_dir):
    response = _transcribe(client, b"hi", content_type="text/plain", filename="a.txt")

    assert response.status_code == 400
    assert not upload_dir.exists() or list(upload_dir.iterdir()) == []
