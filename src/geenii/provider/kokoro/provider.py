import os
from pathlib import Path

from openai import OpenAI

from geenii.datamodels import AudioSpeechGenerationApiResponse
from geenii.provider.interfaces import AISpeechGeneratorProvider


class KokoroProvider(AISpeechGeneratorProvider):

    def __init__(self, **kwargs):
        super().__init__(name="openai")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            return OpenAI(api_key="no-key", base_url="http://localhost:33300/api/v1")
        return self._client

    def generate_speech(self, model: str, text: str, **kwargs) -> AudioSpeechGenerationApiResponse:
        response = self.client.audio.speech.create(
            model="model_q8f16",
            voice="af_heart",
            input="Today is a wonderful day to build something people love!",
        )

        # get base64 content from response
