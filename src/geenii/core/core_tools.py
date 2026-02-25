import subprocess

from geenii.tools import ToolRegistry

geenii_tools = ToolRegistry()

@geenii_tools.tool()
def echo(message: str) -> str:
    """
    A simple echo function that returns the input message.

    :param message: The message to echo.
    :return: The echoed message.
    """
    return f"Echo: {message}"


@geenii_tools.tool()
def reverse_string(text: str) -> str:
    """
    Reverse the input string.

    :param text: The string to reverse.
    :return: The reversed string.
    """
    return text[::-1]


@geenii_tools.tool()
def greet(name: str) -> str:
    """
    Generate a greeting message for the given name.

    :param name: The name to greet.
    :return: A greeting message.
    """
    return f"Hello, {name}!"


@geenii_tools.tool()
def file_exists(file_path: str) -> bool:
    """
    Check if a file exists at the specified path.

    :param file_path: The path to the file to check.
    :return: True if the file exists, False otherwise.
    """
    import os
    return os.path.isfile(file_path)


@geenii_tools.tool()
def file_read(file_path: str) -> str:
    """
    Read and return the contents of a file.

    :param file_path: The path to the file to read.
    :return: The contents of the file as a string.
    """
    with open(file_path, "r") as f:
        return f.read()


@geenii_tools.tool()
def file_write(file_path: str, contents: str) -> None:
    """
    Write the specified contents to a file.

    :param file_path: The path to the file to write to.
    :param contents: The contents to write to the file.
    """
    with open(file_path, "w") as f:
        f.write(contents)


@geenii_tools.tool()
def execute_command(command: str) -> str:
    """
    Execute a shell command and return its output.
    Especially useful for executing AppleScript commands on MacOSX using the "osascript" command.

    :param command: The shell command to execute.
    :return: The output of the command as a string.
    """
    # todo: implement tool usage policy
    allowed_commands = ["ls", "pwd", "whoami", "date", "osascript", "echo", "cat", "head", "tail"]
    if not any(command.startswith(allowed) for allowed in allowed_commands):
        return f"Error: Command '{command}' is not allowed."

    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    # debug print the command, return code, stdout and stderr
    print(f">Executed command: {command}")
    print(f">Return code: {result.returncode}")
    print(f">Standard output: {result.stdout}")
    print(f">Standard error: {result.stderr}")

    return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()


# @geenii_tools.tool()
# def schedule_command(command: str, delay_seconds: int) -> str:
#     """
#     Schedule a shell command to be executed after a specified delay.
#
#     :param command: The shell command to execute.
#     :param delay_seconds: The delay in seconds before executing the command.
#     :return: A message indicating that the command has been scheduled.
#     """
#     import threading
#     def delayed_execution():
#         print(f">Executing scheduled command after {delay_seconds} seconds: {command}")
#         execute_command(command)
#
#     timer = threading.Timer(delay_seconds, delayed_execution)
#     timer.start()
#
#     return f"Command '{command}' scheduled to run in {delay_seconds} seconds."


@geenii_tools.tool()
def display_desktop_notification(message: str, title: str = "Message from Geenii") -> str:
    """
    Show a desktop notification with the given title and message.

    :param message: The message body of the notification.
    :param title: The title of the notification.
    :return: A message indicating that the notification has been sent.
    """
    #command = f"""osascript -e 'display notification "{message}" with title "{title}"'"""
    command = f"""osascript -e 'display dialog "{message}" with title "{title}"'"""
    print(">Displaying desktop notification with command:", command)
    subprocess.run(command, shell=True)

    return "Notification sent."