from geenii.chat.memory import ChatMemory
from geenii.chat.models import ChatMessage, ChatMessageContent
from geenii.datamodels import CompletionApiResponse
from geenii.wizard.completion import CompletionWizard


class DefaultWizard(CompletionWizard):
    """
    A default AI wizard that returns the prompt as is.
    """
    DEFAULT_MODEL = "ollama:mistral:latest"

    def __init__(self,
                 model: str = None,
                 memory: ChatMemory = None,
                 tools=None,
                 context_id=None, **kwargs):
        super().__init__(name="Default Wizard",
                         model=model if model is not None else self.DEFAULT_MODEL,
                         **kwargs)
        self.memory = memory
        self.context_id = context_id
        self.tools = tools if tools is not None else []

    def prompt(self, prompt: str, **kwargs) -> CompletionApiResponse:
        # add prompt to memory
        if self.memory:
            self.memory.add_message(ChatMessage(role="user", content=[
                ChatMessageContent(type="text", text=prompt)
            ]))

        # first we need to figure out what the prompt is asking for
        # does the prompt match any known patterns?
        # does a tool need to be invoked?
        # does the prompt require memory?
        # does a specific model need to be used?
        # does a specific wizard need to be invoked?
        # does a task with multiple steps need to be created/executed?
        result = super().prompt(prompt, **kwargs)
        print("DEFAULT WIZARD PROMPT RESULT:", result)
        # todo add response to memory
        if self.memory:
            if result.output and len(result.output) > 0 \
                and result.output[0].get("content", []) \
                and result.output[0].get("content")[0]["type"] == "output_text":
                self.memory.add_message(ChatMessage(role="assistant", content=[
                    ChatMessageContent(type="text", text=result.output[0].get("content")[0]["text"])
            ]))
        return result
