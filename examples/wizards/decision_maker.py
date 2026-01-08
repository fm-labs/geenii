from typing import List

from geenii.wizard.completion import CompletionWizard


class DecisionMakerWizard(CompletionWizard):
    """
    An AI wizard for make a decision based on the provided prompt and choices.
    """

    def __init__(self, choices: List[str]=None, strict: bool = True, **kwargs):
        super().__init__(
            name="Decision Maker Wizard",
            **kwargs
        )
        self.choices = choices
        if not self.choices or not isinstance(self.choices, list) or len(self.choices) == 0:
            raise ValueError("Choices must be a non-empty list of strings.")
        self.strict = strict
        self.system = self._build_system_prompt()

        # apply default kwargs for the model
        self.model_parameters.update({
            'system': self.system,
            #'output_format': 'json_object',  # Default output format
            'temperature': 0.3,  # Low temperature for deterministic output
            'top_p': 0.3,  # Low top_p for deterministic output
        })

    def prompt(self, prompt: str, **kwargs) -> str | None:
        _prompt = self._build_user_prompt(prompt)
        #print("GENERATE DECISION MAKER WIZARD", kwargs)
        _response = super().prompt(prompt=_prompt, **kwargs)
        print(_response.output[0])
        choice = _response.output[0].get('content', [])[0].get('text', '')

        # Clean and validate the choice
        choice = choice.strip().strip('.!?').upper()
        if choice not in self.choices:
            print(f"Response for {prompt}: '{choice}' is not in the list of choices: {self.choices}.")
            choice = None

        elif self.strict and choice is None:
            raise ValueError(f"Response for {prompt}: '{choice}' is not in the list of choices: {self.choices}.")

        return choice

    def _build_system_prompt(self) -> str:
        """
        Build the full prompt for the AI model including system and user prompts.
        """
        prompt_template = """
You are a helpful AI assistant designed to make decisions based on user prompts.
Analyze the prompt and choose the best option from the provided choices.

Available choices are:
@@@CHOICES@@@

The response MUST be in the list of choices.
The response MUST be one of the choices.
The reponse MUST be exactly one word from the choices.
If the prompt does not match any choice, respond with 'CONFUSED'.
        """

        choices_text = ""
        i = 1
        for choice in self.choices:
            choices_text += f"- {choice}\n"
            i += 1

        return prompt_template.replace("@@@CHOICES@@@", choices_text)

    def _build_user_prompt(self, prompt: str) -> str:
        """
        Build the full prompt for the AI model including system and user prompts.
        """
        return f"""
{prompt}
        """


if __name__ == "__main__":
    # todo : add proper tests
    examples = [
        # Programming decision example
        ("Choose a programming language for web rest api with fast prototyping frameworks and a big developer ecosystem", ["PYTHON", "JAVA", "C++", "JAVASCRIPT", "TYPESCRIPT", "ADA", "OTHER"]),
        ("Choose a programming language for doing machine learning", ["PYTHON", "JAVA", "C++", "JAVASCRIPT", "TYPESCRIPT", "ADA", "OTHER"]),
        ("Choose a programming language for programming smart card chips", ["PYTHON", "JAVA", "C++", "JAVASCRIPT", "TYPESCRIPT", "ADA", "OTHER"]),
        # Tool choice decision example
        ("Choose the best tool for copying a file from one local directory to another", ["RSYNC", "SCP", "CP", "MV", "TAR", "ZIP", "UNZIP", "OTHER"]),
        ("Choose the best tool for copying a file from a local directory to a remote host", ["RSYNC", "SCP", "CP", "MV", "TAR", "ZIP", "UNZIP", "OTHER"]),
        ("Choose the best tool for calculating two numbers", ["GET_WEATHER", "ADD", "FOO", "MV", "TAR", "ZIP", "UNZIP", "OTHER"]),
        ("Choose the best tool for packing files into an archive", ["GET_WEATHER", "ADD", "FOO", "MV", "TAR", "ZIP", "UNZIP", "OTHER"]),
        ("Choose the best tool unpacking files from an archive", ["GET_WEATHER", "ADD", "FOO", "MV", "TAR", "ZIP", "UNZIP", "OTHER"]),
    ]

    for prompt, choices in examples:
        model = "ollama:mistral:latest"
        #model = "ollama:llama3.2:3b"
        #model = "ollama:phi3:latest"
        #model = "openai:gpt-4o-mini"

        wizard = DecisionMakerWizard(choices=choices, model=model)
        choice = wizard.prompt(prompt, strict=False)
        print(f"Prompt: {prompt}\nChoices: {choices}\nResponse: {choice}\n")