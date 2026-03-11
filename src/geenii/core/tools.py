import os
import subprocess
import uuid
import asyncio
import shlex

from geenii.config import DATA_DIR
from geenii.sandbox import run_docker_sandbox_python
from geenii.tool.registry import ToolRegistry

geenii_tools = ToolRegistry()

@geenii_tools.tool()
def file_exists(file_path: str) -> bool:
    """
    Check if a file exists at the specified path.

    :param file_path: The path to the file to check.
    :return: True if the file exists, False otherwise.
    """
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
def execute_command(command: str, skill: str | None = None) -> str:
    """
    Execute a shell command on the local machine and return its output.

    :param command: The shell command to execute. The command should be a single string, e.g. "ls -la /tmp".
    :param skill: The name of the skill that is requesting the command execution.
    :return: The output of the command as a string.
    """
    # todo: implement tool usage policy
    #allowed_commands = ["ls", "pwd", "whoami", "date", "osascript", "echo", "cat", "head", "tail"]
    #if not any(command.startswith(allowed) for allowed in allowed_commands):
    #    return f"Error: Command '{command}' is not allowed."

    working_directory = os.getcwd()
    _env = {}
    if skill:
        skill_dir = f"{DATA_DIR}/skills/{skill}"
        #if os.path.isdir(skill_dir):
        #    working_directory = skill_dir
        _env.update({"SKILL_NAME": skill, "SKILL_DIR": skill_dir})

    # Special handling of python commands to run them in a sandboxed environment
    # if command.startswith("python3 ") or command.startswith("python "):
    #     parts = shlex.split(command)
    #     script_path = parts[1]
    #     args = " ".join(parts[2:])
    #     return execute_python(script_path=script_path, args=args, skill=skill)


    use_supervisor = os.environ.get("USE_SUPERVISOR", "false").lower()  == "true"
    async def run_with_supervisor(cmd, env, cwd):
        #supervisor = g.SUPERVISOR
        name = f"execute-command-{uuid.uuid4().hex}"
        #await supervisor.ensure(name, ProcConfig(name=name,cmd=cmd, env=env, cwd=cwd, restart=False))
        #await supervisor.run(cmd=cmd, env=env, cwd=cwd)
        print(f">Supervisor command return code: {result.returncode}")
        print(f">Supervisor command stdout: {result.stdout}")
        print(f">Supervisor command stderr: {result.stderr}")
        return result

    if use_supervisor:
        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(run_with_supervisor(command, _env, working_directory))
    else:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, env=_env, cwd=working_directory)
        # debug print the command, return code, stdout and stderr
        print(f">Executed command: {command}", f"in directory: {working_directory}", f"with environment: { _env}")
        print(f">Return code: {result.returncode}")
        print(f">Standard output: {result.stdout}")
        print(f">Standard error: {result.stderr}")

    return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()


@geenii_tools.tool()
def execute_applescript(script: str) -> str:
    """
    Execute an AppleScript command on MacOSX and return its output.

    :param script: The AppleScript command to execute.
    :return: The output of the command as a string.
    """
    command = f"""osascript -e '{script}'"""
    print(">Executing AppleScript with command:", command)
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    print(f">Executed AppleScript: {script}")
    print(f">Return code: {result.returncode}")
    print(f">Standard output: {result.stdout}")
    print(f">Standard error: {result.stderr}")

    return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()


@geenii_tools.tool()
def execute_python(script_path: str, args: str = '') -> str:
    """
    Execute a Python script and return its output.

    :param script_path: The path to the Python script to execute.
    :param args: Additional arguments to pass to the Python script as a single string, e.g. "--option value".
    :return: The output of the command as a string.
    """
    print(">Executing Python script with path:", script_path, "and args:", args)

    # replace environment variables in the script path and args
    script_path = os.path.expandvars(script_path)
    args = os.path.expandvars(args)

    script_dir = os.path.dirname(script_path)
    script_name = os.path.basename(script_path)
    script_args = shlex.split(args)
    rc, stdout, stderr = run_docker_sandbox_python(script_dir, script_name,
                                                   script_args=script_args,
                                                   network_mode="bridge", timeout=10)

    print(f">Return code: {rc}")
    print(f">Standard output: {stdout}")
    print(f">Standard error: {stderr}")

    return stdout.strip() if rc == 0 else stderr.strip()


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
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    print(f">Executed notification command: {command}")
    print(f">Return code: {result.returncode}")
    print(f">Standard output: {result.stdout}")
    print(f">Standard error: {result.stderr}")

    return f"Notification sent: {title} - {message}" if result.returncode == 0 else f"Failed to send notification: {result.stderr.strip()}"


@geenii_tools.tool()
def get_weather_forecast(location: str) -> str:
    """
    Get the current weather forecast for a specified location.

    :param location: The location to get the weather forecast for.
    :return: A string containing the weather forecast information.
    """
    # Placeholder implementation - replace with actual API call to a weather service
    return f"The current weather in {location} is sunny with a high of 25°C and a low of 15°C."