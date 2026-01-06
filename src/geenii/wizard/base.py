import abc
from typing import Generator


class BaseWizard(abc.ABC):

    """
    An abstract base class for AI wizards that can be extended to create specific wizards for various tasks.
    An AI wizard is a specialized tool designed to assist with specific tasks or domains.
    Each wizard can use its own model, tools, and methods to achieve its goals.
    """
    @abc.abstractmethod
    def prompt(self, prompt: str, **kwargs):
        """
        Abstract method to be implemented by subclasses to handle the AI query.
        """
        pass

    # @abc.abstractmethod
    # def input(self, prompt: str, **kwargs) -> Generator[dict, None, None]:
    #     pass