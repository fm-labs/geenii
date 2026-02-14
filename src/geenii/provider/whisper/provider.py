from geenii.provider.interfaces import AIAudioTranscriptionProvider, AIAudioTranslationProvider


class WhisperProvider(AIAudioTranscriptionProvider, AIAudioTranslationProvider):
    """
    Whisper provider for audio transcription.
    Uses whispercpp for transcription and translation.
    """


    def __init__(self, model_id: str):
        super().__init__(model_id=model_id)
        self.provider_name = "whisper"
        self.model_id = model_id
        self.model = None  # Placeholder for the actual model instance
        self._initialize_model()

    def _initialize_model(self):
        # Initialize the Hugging Face model here
        pass


    def generate_audio_transcription(self, audio: bytes, **kwargs):
        pass

    def generate_audio_translation(self, audio: bytes, target_language: str, **kwargs):
        pass