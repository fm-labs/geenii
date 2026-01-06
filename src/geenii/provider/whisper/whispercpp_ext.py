import subprocess
import os
from os.path import realpath
import json

from geenii.settings import WHISPERCPP_IMAGE


def run_whisper_cli_transcribe(input_file: str, input_dir: str = "audios",
                               model_dir: str = "models", model_file="ggml-base.bin",
                               output_dir: str = "audios", output_file=None, output_format="json") -> str | dict:
    """
    Run the whisper-cli Docker container to transcribe audio files.

    :param input_file: Name of the input audio file to be transcribed. (e.g., 'input.wav')
    :param input_dir: Directory containing the input audio file. (absolute or relative path)
    :param model_dir: Directory containing the Whisper model file. (absolute or relative path)
    :param model_file: Name of the Whisper model file. (e.g., 'ggml-base.bin')
    :param output_format: Format of the output transcription (e.g., 'json', 'json-full', 'txt', 'csv', 'vtt', 'srt', 'lrc', 'words').
    :param output_file: Name of the output file to save the transcription. (without extension)
    :param output_dir: Directory to save the output transcription file. (absolute or relative path)

    :return: Transcription result as a string or dictionary, depending on the output format.
    :raises FileNotFoundError: If the model directory or input file does not exist.
    :raises RuntimeError: If the whisper-cli command fails.
    """
    if not os.path.exists(model_dir):
        raise FileNotFoundError(f"Model directory does not exist: {model_dir}")
    if not os.path.exists(os.path.join(model_dir, model_file)):
        raise FileNotFoundError(f"Model file does not exist: {os.path.join(model_dir, model_file)}")

    if not os.path.exists(input_dir):
        raise FileNotFoundError(f"Input directory does not exist: {input_dir}")
    if not os.path.exists(os.path.join(input_dir, input_file)):
        raise FileNotFoundError(f"Input file does not exist: {os.path.join(input_dir, input_file)}")

    if output_file is None:
        base_name, _ = os.path.splitext(input_file)
        output_file = f"{base_name}_output"

    # model_file = "ggml-base.bin"
    # output_file = "input.wav"
    whisper_cmd = f"whisper-cli -m /models/{model_file} -f /audios/{input_file} --output-{output_format} --output-file /output/{output_file} --font-path /audios/CourierNewBold.ttf --temperature 0.0 --language en"

    command = ["docker", "run", "--rm",
               "-v", f"{realpath(model_dir)}:/models:ro",
               "-v", f"{realpath(input_dir)}:/audios:ro",
               "-v", f"{realpath(output_dir)}:/output:rw", ]

    # if output_format == "words":
    #    # add ttf font mount for karaoke output
    #    command += ["-v", f"{realpath(input_dir)}:/fonts/CourierNewBold.ttf"]

    command += [WHISPERCPP_IMAGE, whisper_cmd]
    print(f"Running {" ".join(command)}")

    p = subprocess.run(command, capture_output=True)
    print(f"Return code: {p.returncode}")
    if p.returncode != 0:
        print(p.stderr.decode("utf-8"))
        raise RuntimeError(f"Whisper CLI failed with return code {p.returncode}. "
                           f"Command: {' '.join(command)}")

    stdout = p.stdout.decode("utf-8").strip()
    stderr = p.stderr.decode("utf-8").strip()
    print(f"whispercpp-cli stdout: {stdout}")
    print(f"whispercpp-cli stderr: {stderr}")

    # Read the transcription output
    if output_format == "json-full":
        output_format = "json"
    if output_format == "words":
        output_format = "wts"
    output_path = os.path.join(input_dir, f"{output_file}.{output_format}")
    if not os.path.exists(output_path):
        raise FileNotFoundError(f"Output file was not created: {output_path}")

    transcription = None
    with open(output_path, 'r') as f:
        transcription = f.read().strip()

    if output_format == "json":  # or output_format == "json-full":
        try:
            transcription = json.loads(transcription)
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse JSON output: {e}")

    return transcription


def run_whisper_server_in_docker(model_dir: str = "models", model_file="ggml-base.bin") -> None:
    """
    Run the whisper-server in Docker container to transcribe audio files.

    :param model_dir: Directory containing the Whisper model file. (absolute or relative path)
    :param model_file: Name of the Whisper model file. (e.g., 'ggml-base.bin')

    :raises FileNotFoundError: If the model directory or input file does not exist.
    :raises RuntimeError: If the whisper-cli command fails.
    """
    if not os.path.exists(model_dir):
        raise FileNotFoundError(f"Model directory does not exist: {model_dir}")
    if not os.path.exists(os.path.join(model_dir, model_file)):
        raise FileNotFoundError(f"Model file does not exist: {os.path.join(model_dir, model_file)}")

    whisper_cmd = f"whisper-server -m /models/{model_file} --host 0.0.0.0 --port 8766 --language en"

    command = ["docker", "run", "--rm",
               #"--gpus", "all",
               "-v", f"{realpath(model_dir)}:/models:ro",
               "-p", "8766:8766",]

    command += [WHISPERCPP_IMAGE, whisper_cmd]
    print(f"Running {' '.join(command)}")

    p = subprocess.run(command, capture_output=True)
    print(f"Return code: {p.returncode}")
    if p.returncode != 0:
        print(p.stderr.decode("utf-8"))
        raise RuntimeError(f"Whisper Server failed with return code {p.returncode}. "
                           f"Command: {' '.join(command)}")

    stdout = p.stdout.decode("utf-8").strip()
    stderr = p.stderr.decode("utf-8").strip()
    print(f"whispercpp-cli stdout: {stdout}")
    print(f"whispercpp-cli stderr: {stderr}")
