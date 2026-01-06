# Install kokoro
#pip install -q kokoro>=0.9.4 soundfile
# Install espeak, used for English OOD fallback and some non-English languages
#apt-get -qq -y install espeak-ng > /dev/null 2>&1

from os.path import splitext
from typing import List, Any

import numpy as np
# Initialize a pipeline
from kokoro import KPipeline
from IPython.display import display, Audio
import soundfile as sf
import torch
# 🇺🇸 'a' => American English,
# 🇬🇧 'b' => British English
# 🇪🇸 'e' => Spanish es
# 🇫🇷 'f' => French fr-fr
# 🇮🇳 'h' => Hindi hi
# 🇮🇹 'i' => Italian it
# 🇯🇵 'j' => Japanese: pip install misaki[ja]
# 🇧🇷 'p' => Brazilian Portuguese pt-br
# 🇨🇳 'z' => Mandarin Chinese: pip install misaki[zh]


def run_tts_pipeline(input_text: str, output_file: str, lang_code: str = 'a'):
    """
    :param input_text: Text to be converted to speech.
    :param output_file: Path to save the generated audio file.
    :return:
    """

    pipeline = KPipeline(lang_code=lang_code) # <= make sure lang_code matches voice, reference above.

    # 4️⃣ Generate, display, and save audio files in a loop.
    generator = pipeline(
        input_text,
        voice='af_heart', # <= change voice here
        speed=1,
        split_pattern=r'\n+'
    )

    # Alternatively, load voice tensor directly:
    # voice_tensor = torch.load('path/to/voice.pt', weights_only=True)
    # generator = pipeline(
    #     text, voice=voice_tensor,
    #     speed=1, split_pattern=r'\n+'
    # )

    base,ext = splitext(output_file)

    chunks: List[Any] = []
    for i, (gs, ps, audio) in enumerate(generator):
        chunk_file = f"{base}_{i}{ext}"
        print(i)  # i => index
        print(gs) # gs => graphemes/text
        print(ps) # ps => phonemes
        display(Audio(data=audio, rate=24000, autoplay=i==0))
        print(f"Generating chunk {chunk_file}")
        sf.write(chunk_file, audio, 24000) # save each audio file
        chunks.append(audio)

    # Merge
    if len(chunks) > 0:
        print(f"Merging {len(chunks)} audio chunks into {output_file}")
        merged_audio = np.concatenate(chunks)
        #merged_audio = torch.cat(merged_audio, dim=0)
        sf.write(output_file, merged_audio, 24000)
        print(f"Saved merged audio to {output_file}")
