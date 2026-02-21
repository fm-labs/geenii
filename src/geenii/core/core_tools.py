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
def file_read_bytes(file_path: str) -> bytes:
    """
    Read and return the contents of a file as bytes.

    :param file_path: The path to the file to read.
    :return: The contents of the file as bytes.
    """
    with open(file_path, "rb") as f:
        return f.read()


@geenii_tools.tool()
def file_write_bytes(file_path: str, contents: bytes) -> None:
    """
    Write the specified bytes contents to a file.

    :param file_path: The path to the file to write to.
    :param contents: The bytes contents to write to the file.
    """
    with open(file_path, "wb") as f:
        f.write(contents)


@geenii_tools.tool()
def execute_command(command: str) -> str:
    """
    Execute a shell command and return its output.

    :param command: The shell command to execute.
    :return: The output of the command as a string.
    """
    import subprocess
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()


@geenii_tools.tool()
def bash(command: str) -> str:
    """
    Alias for execute_command to run a bash command.

    :param command: The bash command to execute.
    :return: The output of the command as a string.
    """
    return execute_command(command)