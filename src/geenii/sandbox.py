import subprocess


def run_docker_subprocess(command: list[str], timeout: int = 30) -> tuple[int, str, str]:
    """
    Run a subprocess command with a timeout and return the exit code, stdout, and stderr.

    Args:
        command (list[str]): The command to run as a list of strings.
        timeout (int): The maximum time to allow the command to run in seconds.

    Returns:
        tuple[int, str, str]: A tuple containing the exit code, stdout, and stderr.
    """
    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as e:
        return -1, "", f"Command timed out after {timeout} seconds"
    except Exception as e:
        return -1, "", f"Error running command: {str(e)}"


def run_docker_sandbox_python(base_dir: str, script_name: str = "main.py", script_args: list[str] = None,
                              mounts: list[str] = None, timeout: int = 30,) -> tuple[int, str, str]:
    """
    Run a Python script in a Docker sandbox.

    :param base_dir: The base directory containing the script to run.
    :param script_name: The name of the Python script to run (default: "main.py").
    :param script_args: List of additional arguments to pass to the Python script (default: None).
    :param mounts: A list of additional mount points in the format "host_path:container_path" (default: None).
    :param timeout: The maximum time to allow the command to run in seconds (default: 30).
    :return: A tuple containing the exit code, stdout, and stderr.
    """

    command = ["docker", "run", "--rm"]
    if mounts:
        for mount in mounts:
            command.extend(["-v", mount])
    command.extend(["-v", f"{base_dir}:/app:ro"])
    command.extend(["-w", "/app"])
    command.append("python:3.13-slim")
    command.extend(["python3", script_name])
    if script_args:
        command.extend(script_args)

    return run_docker_subprocess(command, timeout)

