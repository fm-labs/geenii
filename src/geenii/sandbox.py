import subprocess
import os
import time
from typing import Literal

SANDBOX_PYTHON3_BASEIMAGE = "python:3.13-slim"

def run_docker_subprocess(command: list[str], timeout: int = 30, env: dict | None = None) -> tuple[int, str, str]:
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
            timeout=timeout,
            env=env,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired as e:
        return -1, "", f"Command timed out after {timeout} seconds"
    except Exception as e:
        return -1, "", f"Error running command: {str(e)}"


def run_docker_sandbox_python(base_dir: str, script_name: str = "main.py", script_args: list[str] = None,
                              mounts: list[str] = None,
                              network_mode: Literal["none", "bridge", "host"] = "none",
                              cap_add: list[str] = None,
                              cpu_limit: float = 0.5, mem_limit: str = "256m", pid_limit: int = 100,
                              timeout: int = 30, env: dict | None = None) -> tuple[int, str, str]:
    """
    Run a Python script in a Docker sandbox.

    :param base_dir: The base directory containing the script to run.
    :param script_name: The name of the Python script to run (default: "main.py").
    :param script_args: List of additional arguments to pass to the Python script (default: None).
    :param mounts: A list of additional mount points in the format "host_path:container_path" (default: None).
    :param network_mode: The Docker network mode to use (default: "none" for no network access).
    :param cap_add: A list of Linux capabilities to add to the container (default: None). Note: cap_drop ALL is used by default to drop all capabilities.
    :param cpu_limit: The CPU limit for the container (default: 0.5 for 50% of a single CPU core).
    :param mem_limit: The memory limit for the container (default: "256m" for 256 MB of RAM).
    :param pid_limit: The maximum number of processes allowed in the container (default: 100).
    :param timeout: The maximum time to allow the command to run in seconds (default: 30).
    :return: A tuple containing the exit code, stdout, and stderr.
    """
    print(f"Running Docker sandbox with base_dir={base_dir}, script_name={script_name}, script_args={script_args},"
          f" mounts={mounts}, timeout={timeout}")

    if not os.path.exists(base_dir):
        raise ValueError(f"Base directory does not exist: {base_dir}")

    command = ["docker", "run", "--rm"]
    # Mount the base directory as read-only and set as working directory
    command.extend(["-v", f"{base_dir}:/app:ro"])
    command.extend(["-w", "/app"])

    # Mounts
    if mounts:
        for mount in mounts:
            command.extend(["-v", mount])

    # Mount a tmpfs for /tmp to allow write operations without affecting the host filesystem
    command.extend(["-v", "tmpfs:/tmp"])

    # Readonly root filesystem
    command.append("--read-only")

    # Networking
    # --network none = No network access.
    # --network host = Use the host's network stack (not recommended for untrusted code).
    # --network bridge = Default Docker network (isolated, but allows outbound access).
    # --network <custom> = Use a custom Docker network with specific rules.
    command.extend(["--network", network_mode])

    # Non-root user (nobody)
    command.extend(["--user", "nobody"])

    # Resource limits (optional, but recommended)
    # CPU limit: --cpus="0.5" limits the container to 50% of a single CPU core.
    # Memory limit: --memory="256m" limits the container to 256 MB of RAM.
    # PID limit: --pids-limit=100 limits the container to 100 processes
    if cpu_limit is not None:
        command.extend(["--cpus", str(cpu_limit)])
    if mem_limit is not None:
        command.extend(["--memory", str(mem_limit)])
        command.extend(["--memory-swap", str(mem_limit)])  # prevent using swap beyond the memory limit
    if pid_limit is not None:
        command.extend(["--pids-limit", str(pid_limit)]) # prevent fork bombs and excessive process creation

    # Capabilities
    # --cap-drop ALL is used to drop all Linux capabilities from the container
    # --cap-drop NET_ADMIN is used to drop the NET_ADMIN capability.
    # --cap-add can be used to add specific capabilities if needed (e.g., --cap-add SYS_ADMIN for certain operations).
    # List of capabilities:
    # - NET_ADMIN allows network configuration (not needed for our sandbox).
    # - SYS_ADMIN allows a wide range of administrative operations (not needed for our sandbox).
    # - ALL drops all capabilities, which is a good default for untrusted code.
    # For more details on Docker capabilities, see:
    # https://docs.docker.com/engine/reference/run/#runtime-privilege-and-linux-capabilities
    command.extend(["--cap-drop", "ALL"])
    if cap_add:
        for cap in cap_add:
            command.extend(["--cap-add", cap])
    # no new privileges
    # https://raesene.github.io/blog/2019/06/01/docker-capabilities-and-no-new-privs/
    #command.extend(["--security-opt=no-new-privileges:true"])

    # OOM killer: --oom-kill-disable prevents the container from being killed by the OOM killer, but use with caution as it may lead to resource exhaustion.
    # command.append("--oom-kill-disable")

    # python image and command
    command.append(SANDBOX_PYTHON3_BASEIMAGE)
    command.extend(["python3", script_name])
    if script_args:
        command.extend(script_args)

    print(f"Running command: {' '.join(command)}")
    start_time = time.time()
    result = run_docker_subprocess(command, timeout=timeout, env=env)
    end_time = time.time()
    print(f"Command finished in {end_time - start_time:.8f} seconds with exit code {result[0]}")
    return result

