from geenii import settings
from geenii.ai import get_ai_provider
from geenii.datamodels import CompletionResponse, CompletionRequest
from geenii.provider.interfaces import AIProvider, AICompletionProvider
from geenii.service import generate_completion
from geenii.util import split_model
from geenii.wizard.base import BaseWizard


class CompletionWizard(BaseWizard):
    """
    A base class for AI wizards that can be extended to create specific wizards for various tasks.
    An AI wizard is a specialized tool designed to assist with specific tasks or domains.
    Each wizard can use its own model, tools, and methods to achieve its goals.
    """
    ai: AIProvider

    def __init__(self,
                 name: str,
                 model=settings.DEFAULT_COMPLETION_MODEL,
                 model_parameters: dict = None,
                 system: str = None,
                 output_format: str = None, **kwargs):
        self.name = name
        self.model_id = model
        self.system = system
        self.output_format = output_format
        self.model_parameters = model_parameters if model_parameters is not None else {}

        # initialize model provider and name
        provider_name, model_name = split_model(model)
        if provider_name is None or model_name is None:
            raise ValueError("Model must be specified in the format 'provider/model_name'.")

        #self.ai = get_ai_provider(provider_name)
        #self.model_name = model_name
        #self.model_parameters = kwargs

    def __str__(self):
        out = f"{self.__class__.__name__}(name={self.name}, model={self.model_id}, tools={len(self.tools)}, output_format={self.output_format}"
        # if self.system:
        #     out += f", system={len(self.system)}" # only length for system prompt
        # if self.model_kwargs:
        #     out += f", model_kwargs={self.model_kwargs}"
        # out += ")"
        return out

    def __repr__(self):
        return self.__str__()

    def prompt(self, prompt: str, **kwargs) -> CompletionResponse:
        #if not isinstance(self.ai, AICompletionProvider):
        #    raise TypeError("AI provider must implement AICompletionProvider to run the wizard.")

        if prompt is None or prompt.strip() == "":
            raise ValueError("No prompt provided.")

        # Call the AI provider to get a response
        completion_kwargs = self.model_parameters.copy()
        completion_kwargs.update({
            'model': self.model_id,
            'system': self.system,
            'output_format': self.output_format
        })
        completion_kwargs.update(kwargs)
        #response = self.ai.generate_completion(prompt=prompt, **completion_kwargs)
        request = CompletionRequest(prompt=prompt, **completion_kwargs)
        response = generate_completion(request)
        #if not isinstance(response, CompletionResponse):
        #    raise TypeError("AI provider did not return a valid CompletionResponse.")

        return response
