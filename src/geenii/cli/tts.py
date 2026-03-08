import subprocess


def tts_say_cli(message: str, max_length: int = 500, speaking_rate: float = 1.0, voice: str = None):
    """
    Execute the "say" command on MacOSX to speak the message.

    :param message: The message to speak.
    :param max_length: Max length
    :param speaking_rate: Speaking rate. Default is 1.0 (normal speed = 175 words per minute).
    :param voice: Name of the voice to use. Defaults to system voice. You can list available voices with "say -v '?'".
    :return:
    """
    if len(message) > max_length:
        message = message[:max_length] + " (message to long, truncated)"

    print(f"SAY: {message}")
    cmd = ["say", '-r', str(int(175 * speaking_rate))]
    if voice:
        cmd.extend(['-v', voice])
    cmd.append(message)
    subprocess.run(cmd)


def tts_espeak_cli(message: str, max_length: int = 500, speaking_rate: float = 1.0, voice: str = None):
    """
    Execute the "espeak" command on Linux to speak the message.

    :param message: The message to speak.
    :param max_length: Max length
    :param speaking_rate: Speaking rate. Default is 1.0 (normal speed = 175 words per minute).
    :param voice: Name of the voice to use. Defaults to system voice. You can list available voices with "espeak --voices".
    :return:
    """
    if len(message) > max_length:
        message = message[:max_length] + " (message to long, truncated)"

    print(f"SAY: {message}")
    cmd = ["espeak", '-s', str(int(175 * speaking_rate))]  # espeak uses words per minute, default is 175 wpm
    if voice:
        cmd.extend(['-v', voice])
    cmd.append(message)
    subprocess.run(cmd)


# def tts_windows(message: str, max_length: int = 500, speaking_rate: float = 1.0, voice: str = None):
#     """
#     Use the Windows SAPI to speak the message.
#
#     :param message: The message to speak.
#     :param max_length: Max length
#     :param speaking_rate: Speaking rate. Default is 1.0 (normal speed).
#     :param voice: Name of the voice to use. Defaults to system voice.
#     :return:
#     """
#     import win32com.client
#
#     if len(message) > max_length:
#         message = message[:max_length] + " (message to long, truncated)"
#
#     print(f"SAY: {message}")
#     speaker = win32com.client.Dispatch("SAPI.SpVoice")
#     if voice:
#         speaker.Voice = speaker.GetVoices().Item(voice)
#     speaker.Rate = int((speaking_rate - 1.0) * 10)  # SAPI uses a rate from -10 to +10, where 0 is normal speed
#     speaker.Speak(message)