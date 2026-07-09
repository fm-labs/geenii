"""Tests for the FakeProvider and agent loop integration."""


from geenii.chat_models import TextContent, ToolCallContent
from geenii.datamodels import ChatCompletionRequest
from geenii.provider.fake.provider import FakeProvider


class TestFakeProvider:

    def test_returns_queued_text(self):
        provider = FakeProvider()
        provider.enqueue("Hello!")

        request = ChatCompletionRequest(prompt="Hi", model="fake:test")
        response = provider.generate_chat_completion(request)

        assert len(response.output) == 1
        assert isinstance(response.output[0], TextContent)
        assert response.output[0].text == "Hello!"

    def test_returns_default_when_queue_empty(self):
        provider = FakeProvider()

        request = ChatCompletionRequest(prompt="Hi", model="fake:test")
        response = provider.generate_chat_completion(request)

        assert response.output[0].text == provider.default_response

    def test_fifo_order(self):
        provider = FakeProvider()
        provider.enqueue("First")
        provider.enqueue("Second")

        r1 = provider.generate_chat_completion(ChatCompletionRequest(prompt="a", model="fake:test"))
        r2 = provider.generate_chat_completion(ChatCompletionRequest(prompt="b", model="fake:test"))

        assert r1.output[0].text == "First"
        assert r2.output[0].text == "Second"

    def test_tool_call_response(self):
        provider = FakeProvider()
        provider.enqueue_tool_call("get_weather", {"city": "Vienna"})

        request = ChatCompletionRequest(prompt="weather?", model="fake:test")
        response = provider.generate_chat_completion(request)

        assert len(response.output) == 1
        tc = response.output[0]
        assert isinstance(tc, ToolCallContent)
        assert tc.name == "get_weather"
        assert tc.arguments == {"city": "Vienna"}

    def test_records_requests(self):
        provider = FakeProvider()
        provider.enqueue("ok")

        request = ChatCompletionRequest(prompt="test prompt", model="fake:test")
        provider.generate_chat_completion(request)

        assert len(provider.requests) == 1
        assert provider.requests[0].prompt == "test prompt"

    def test_reset_clears_state(self):
        provider = FakeProvider()
        provider.enqueue("will be cleared")
        provider.generate_chat_completion(ChatCompletionRequest(prompt="x", model="fake:test"))
        provider.reset()

        assert len(provider.requests) == 0
        assert len(provider._responses) == 0

    def test_usage_stats(self):
        provider = FakeProvider()
        provider.enqueue("ok")

        response = provider.generate_chat_completion(ChatCompletionRequest(prompt="x", model="fake:test"))

        assert response.usage["input_tokens"] == 10
        assert response.usage["output_tokens"] == 20
        assert response.usage["total_tokens"] == 30

    def test_is_configured(self):
        provider = FakeProvider()
        assert provider.is_configured() is True

    def test_get_models(self):
        provider = FakeProvider()
        models = provider.get_models()
        assert len(models) == 1
        assert models[0].name == "test"
        assert models[0].provider == "fake"
