import argparse

if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    subparsers = parser.add_subparsers(dest="command")

    # subparser for "completion" command
    ai_parser = subparsers.add_parser("completion", help="Run AI completion")
    ai_parser.add_argument("--model", type=str, required=True, help="AI model identifier")
    ai_parser.add_argument("--prompt", type=str, required=True, help="Prompt for AI completion")

    # subparser for "whisper" command
    tts_parser = subparsers.add_parser("tts", help="Text-to-Speech using Whisper")
    tts_parser.add_argument("--model-file", type=str, required=True, help="Whisper model file")
    tts_parser.add_argument("--input-file", type=str, required=True, help="Input audio file for transcription")
    tts_parser.add_argument("--output-format", type=str, required=True, help="Output format for transcription")

    args = parser.parse_args()
    print(args)

    print("Not implemented yet.")
