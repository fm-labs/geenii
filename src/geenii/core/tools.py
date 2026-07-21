from pathlib import Path

import subprocess

from geenii import config
from geenii.tool.registry import ToolRegistry

def is_file_in_working_dir(file_path: str) -> bool:
    """Return True if file_path resolves to a location inside the working dir."""
    try:
        wd = Path(config.GEENII_WORKING_DIR).resolve(strict=False)
        target = Path(file_path).resolve(strict=False)
    except (OSError, ValueError):
        # null bytes, embedded NULs, unresolvable paths, symlink loops
        return False
    return target != wd and wd in target.parents


def init_core_tools(tool_registry: ToolRegistry) -> None:

    #tool_registry = ToolRegistry()

    # @tool_registry.tool()
    # def file_exists(file_path: str) -> bool:
    #     """
    #     Check if a file exists at the specified path.
    #
    #     :param file_path: The path to the file to check.
    #     :return: True if the file exists, False otherwise.
    #     """
    #     return os.path.isfile(file_path)


    @tool_registry.tool(name="read")
    def file_read(file_path: str) -> str:
        """
        Read and return the contents of a file.

        :param file_path: The path to the file to read.
        :return: The contents of the file as a string.
        """
        if not is_file_in_working_dir(file_path):
            return "You are not allowed to read this file."

        with open(file_path, "r") as f:
            return f.read()


    @tool_registry.tool(name="write")
    def file_write(file_path: str, contents: str) -> str:
        """
        Write the contents to a file.

        :param file_path: The path to the file to write to.
        :param contents: The contents to write to the file.
        """
        if not is_file_in_working_dir(file_path):
            return "You are not allowed to write this file."

        with open(file_path, "w") as f:
            f.write(contents)

        return f"Contents successfully written to {file_path}"

    #
    # @tool_registry.tool()
    # def bash(command: str, skill: str | None = None) -> str:
    #     """
    #     Execute a shell command on the local machine and return its output.
    #
    #     :param command: The shell command to execute. The command should be a single string, e.g. "ls -la /tmp".
    #     :param skill: The name of the skill that is requesting the command execution.
    #     :return: The output of the command as a string.
    #     """
    #     # todo: implement tool usage policy
    #     #allowed_commands = ["ls", "pwd", "whoami", "date", "osascript", "echo", "cat", "head", "tail"]
    #     #if not any(command.startswith(allowed) for allowed in allowed_commands):
    #     #    return f"Error: Command '{command}' is not allowed."
    #
    #     working_directory = os.getcwd()
    #     _env = {}
    #     if skill:
    #         skill_dir = locate_skill_path(skill)
    #         #if os.path.isdir(skill_dir):
    #         #    working_directory = skill_dir
    #         _env.update({"SKILL_NAME": skill, "SKILL_DIR": skill_dir})
    #
    #     # Special handling of python commands to run them in a sandboxed environment
    #     # if command.startswith("python3 ") or command.startswith("python "):
    #     #     parts = shlex.split(command)
    #     #     script_path = parts[1]
    #     #     args = " ".join(parts[2:])
    #     #     return python(script_path=script_path, args=args, skill=skill)
    #
    #
    #     use_supervisor = os.environ.get("USE_SUPERVISOR", "false").lower()  == "true"
    #     async def run_with_supervisor(cmd, env, cwd):
    #         #supervisor = g.SUPERVISOR
    #         _name = f"execute-command-{uuid.uuid4().hex}"
    #         #await supervisor.ensure(name, ProcConfig(name=name,cmd=cmd, env=env, cwd=cwd, restart=False))
    #         #await supervisor.run(cmd=cmd, env=env, cwd=cwd)
    #         print(f">Supervisor command return code: {result.returncode}")
    #         print(f">Supervisor command stdout: {result.stdout}")
    #         print(f">Supervisor command stderr: {result.stderr}")
    #         return result
    #
    #     if use_supervisor:
    #         loop = asyncio.get_event_loop()
    #         result = loop.run_until_complete(run_with_supervisor(command, _env, working_directory))
    #     else:
    #         result = subprocess.run(command, shell=True, capture_output=True, text=True, env=_env, cwd=working_directory)
    #         # debug print the command, return code, stdout and stderr
    #         print(f">Executed command: {command}", f"in directory: {working_directory}", f"with environment: { _env}")
    #         print(f">Return code: {result.returncode}")
    #         print(f">Standard output: {result.stdout}")
    #         print(f">Standard error: {result.stderr}")
    #
    #     return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    #
    #
    # @tool_registry.tool()
    # def applescript(script: str) -> str:
    #     """
    #     Execute an AppleScript command on MacOSX and return its output.
    #
    #     :param script: The AppleScript command to execute.
    #     :return: The output of the command as a string.
    #     """
    #     command = f"""osascript -e '{script}'"""
    #     print(">Executing AppleScript with command:", command)
    #     result = subprocess.run(command, shell=True, capture_output=True, text=True)
    #     print(f">Executed AppleScript: {script}")
    #     print(f">Return code: {result.returncode}")
    #     print(f">Standard output: {result.stdout}")
    #     print(f">Standard error: {result.stderr}")
    #
    #     return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    #
    #
    # @tool_registry.tool()
    # def python(script_path: str, args: str = '') -> str:
    #     """
    #     Execute a Python script and return its output.
    #
    #     :param script_path: The path to the Python script to execute.
    #     :param args: Additional arguments to pass to the Python script as a single string, e.g. "--option value".
    #     :return: The output of the command as a string.
    #     """
    #     print(">Executing Python script with path:", script_path, "and args:", args)
    #
    #     # replace environment variables in the script path and args
    #     script_path = os.path.expandvars(script_path)
    #     args = os.path.expandvars(args)
    #
    #     script_dir = os.path.dirname(script_path)
    #     script_name = os.path.basename(script_path)
    #     script_args = shlex.split(args)
    #     rc, stdout, stderr = run_docker_sandbox_python(script_dir, script_name,
    #                                                    script_args=script_args,
    #                                                    network_mode="bridge", timeout=10)
    #
    #     print(f">Return code: {rc}")
    #     print(f">Standard output: {stdout}")
    #     print(f">Standard error: {stderr}")
    #
    #     return stdout.strip() if rc == 0 else stderr.strip()


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
    #         bash(command)
    #
    #     timer = threading.Timer(delay_seconds, delayed_execution)
    #     timer.start()
    #
    #     return f"Command '{command}' scheduled to run in {delay_seconds} seconds."


    @tool_registry.tool()
    def display_desktop_notification(message: str, title: str = "Message from Geenii") -> str:
        """
        Show a desktop notification with the given title and message.

        :param message: The message body of the notification.
        :param title: The title of the notification.
        :return: A message indicating that the notification has been sent.
        """
        def _escape_applescript(s: str) -> str:
            return (s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
                    .replace("\r", "\\r").replace("\t", "\\t"))

        script = (
            f'display dialog "{_escape_applescript(message)}"'
            f' with title "{_escape_applescript(title)}"'
            f' buttons {{"OK"}} giving up after 60'
        )
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True
        )
        if result.returncode != 0:
            return f"Failed to send notification: {result.stderr.strip()}"
        return f"Notification sent: {title} - {message}"


    # @tool_registry.tool()
    # def get_weather_forecast(location: str) -> str:
    #     """
    #     Get the current weather forecast for a specified location.
    #
    #     :param location: The location to get the weather forecast for.
    #     :return: A string containing the weather forecast information.
    #     """
    #     # Placeholder implementation - replace with actual API call to a weather service
    #     return f"The current weather in {location} is sunny with a high of 25°C and a low of 15°C."