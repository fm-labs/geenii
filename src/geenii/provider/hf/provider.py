import base64
import os
import tempfile
import time
import uuid

from geenii import settings
from geenii.datamodels import AudioGenerationApiResponse
#from xai.provider.hf.tts_kokoro import run_tts_pipeline
from geenii.provider.interfaces import AIAudioGeneratorProvider


class HuggingFaceAIProvider(AIAudioGeneratorProvider):
    """
    Hugging Face AI provider for audio generation.
    This class extends the AIAudioGeneratorProvider to provide audio generation capabilities using Hugging Face models.
    """

    def __init__(self):
        self.name = "hf"

    def _initialize_model(self):
        pass

    def generate_speech(self, text: str, **kwargs):
        model = kwargs.get("model", settings.DEFAULT_AUDIO_GENERATION_MODEL)
        request_id = str(uuid.uuid4())
        try:
            #tmp_output_file = tempfile.NamedTemporaryFile(delete=True)
            #tmp_file_handle, tmp_output_file = tempfile.mkstemp(suffix='.wav', prefix='xai_audio_')
            output_file = os.path.realpath(os.path.join(settings.DATA_DIR, "tts", f"output_{time.time()}_{request_id}.wav"))
            #run_tts_pipeline(text, output_file, 'a')

            # read the generated audio file
            # encode as base64
            # create data url
            with open(output_file, 'rb') as f:
                audio_data = f.read()

            base64_audio = base64.b64encode(audio_data)
            print("Base64 audio", base64_audio)

            # Clean up the temporary file
            #os.remove(output_file)

            # Return the response in the expected format
            data_url = f"data:audio/wav;base64,{base64_audio.decode('utf-8')}"

            return AudioGenerationApiResponse(
                id=str(uuid.uuid4()),
                timestamp=time.time(),
                model=model,
                provider=self.name,
                text=text,
                output=[{"url": data_url, "base64": base64_audio.decode('utf-8')}],
                #output=[{"base64": base64_audio}],
            )
        except Exception as e:
            raise RuntimeError(f"Failed to generate audio: {str(e)}")
