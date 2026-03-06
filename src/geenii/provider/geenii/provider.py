from geenii.datamodels import ChatCompletionRequest, ChatCompletionResponse, CompletionResponse, AIModelInfo
from geenii.provider.interfaces import AIProvider, AICompletionProvider, AIChatCompletionProvider

class GeeniiProvider(AIProvider, AICompletionProvider, AIChatCompletionProvider):

    def __init__(self):
        super().__init__(name="geenii")

    def is_configured(self) -> bool:
        return True

    def get_capabilities(self) -> list[str]:
        return []

    def get_models(self) -> list[AIModelInfo]:
        return [
            AIModelInfo(
                name="default",
                provider="geenii",
                description="The default agent for general purpose tasks.",
                capabilities=["completion", "chat_completion"],
                locality="mixed",
            )
        ]

    def generate_completion(self, model: str, prompt: str, **kwargs) -> CompletionResponse:
        raise NotImplementedError("Not implemented yet")

    def generate_chat_completion(self, request: ChatCompletionRequest, tool_registry=None) -> ChatCompletionResponse:
        raise NotImplementedError("Not implemented yet")