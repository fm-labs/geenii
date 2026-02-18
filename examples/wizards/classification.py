from geenii import config
from geenii.datamodels import CompletionResponse
from geenii.wizard.completion import CompletionWizard


class NewsClassificationWizard(CompletionWizard):
    """
    An AI wizard for classifying news articles into categories such as 'politics', 'sports', 'entertainment', etc.
    """

    DEFAULT_CLASSIFICATION_MODEL = settings.DEFAULT_COMPLETION_MODEL

    CLASSIFICATION_CATEGORIES = [
        "POLITICS", "BUSINESS", "TECH", "SPORTS", "ENTERTAINMENT",
        "HEALTH", "SCIENCE", "CRIME", "ACCIDENT", "INFORMATIONAL",
        "CHRONIC", "WEATHER", "WORLD", "ART", "PHOTOGRAPHY",
        "WAR", "CULTURE", "EDUCATION", "TRAVEL", "FOOD",
        "FINANCE", "OPINION", "RELIGION", "ENVIRONMENT",
        "ENERGY", "REAL_ESTATE", "AUTOMOTIVE", "OTHER"
    ]

    def __init__(self, model=DEFAULT_CLASSIFICATION_MODEL, output_format="json", **kwargs):
        super().__init__(
            name="News Classification Wizard",
            model=model,
            output_format=output_format,
            **kwargs
        )

    def prompt(self, prompt: str, **kwargs) -> CompletionResponse:
        return super().prompt(
            model=self.model_name,
            format=self.output_format,
            prompt=self._build_prompt(prompt),
            max_tokens=1,  # Enforce single word output
            temperature=0.1,  # Low temperature for deterministic output
            **kwargs
        )

    def _build_prompt(self, prompt: str) -> str:
        """
        Build the full prompt for the AI model including system and user prompts.
        """
        prompt_template = """
        <|system|>
        You are a news classifier. For each headline, respond with exactly one word from a predefined list of categories.

        @@@CATEGORIES@@@

        Choose the best match. Output only the category word.
        If the headline does not match any category, respond with 'OTHER'.
        Output only the category word, nothing else.
        The user will provide news headlines title, nothing else.
        Respond with the category in JSON format with keys 'title', 'category', 'confidence'.
        Set confidence to LOW, MEDIUM or HIGH based on your confidence level.
        Extract 3 most relevant keywords from the headline and return them in a list under 'keywords'.
        <|endofsystem|>

        <|user|>
        @@@PROMPT@@@
        <|endofuser|>
        """
        categories_text = "\n".join(self.CLASSIFICATION_CATEGORIES)
        full_prompt = prompt_template.replace("@@@CATEGORIES@@@", categories_text).replace("@@@PROMPT@@@", prompt)
        return full_prompt.strip()
