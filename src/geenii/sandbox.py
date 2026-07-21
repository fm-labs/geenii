from os.path import dirname

import uuid

import abc

import subprocess
import os
import time
from typing import Literal

from geenii.config import CACHE_DIR

SANDBOX_PYTHON3_BASEIMAGE = "python:3.13-slim"


def run_docker_subprocess(
    command: list[str], timeout: int = 30, env: dict | None = None
) -> tuple[int, str, str]:
    """
    Run a subprocess command with a timeout and return the exit code, stdout, and stderr.

    Args:
        command (list[str]): The command to run as a list of strings.
        timeout (int): The maximum time to allow the command to run in seconds.

    Returns:
        tuple[int, str, str]: A tuple containing the exit code, stdout, and stderr.
    """
    print("RUN COMMAND:", command)
    print("COMMAND ENV", env)

    _env = os.environ.copy()
    if env is not None:
        _env.update(env)

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            env=_env,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Command timed out after {timeout} seconds"
    except Exception as e:
        return -1, "", f"Error running command: {str(e)}"


def build_sandbox_image(
    sandbox_id: str, app_dir: str, env: dict | None = None, dockerlines: str = None
) -> str:
    """
    Build a docker image from base python image + installing deps defined in pyproject.toml file.

    :param sandbox_id:
    :param app_dir:
    :param env:
    :return:
    """
    # sandbox_docker_file = os.path.join(app_dir, "sandbox.Dockerfile")
    sandbox_docker_file = os.path.join(CACHE_DIR, "sandboxes", sandbox_id, "Dockerfile")
    os.makedirs(dirname(sandbox_docker_file), exist_ok=True)
    overwrite = True
    image_name = "geenii-sandbox-" + sandbox_id

    if not dockerlines or len(dockerlines) == 0:
        raise ValueError(f"dockerlines is not defined for sandbox {sandbox_id}")

    if not os.path.isfile(sandbox_docker_file) or overwrite:
        with open(sandbox_docker_file, "w") as f:
            f.write(dockerlines)

    command = ["docker", "build", "-t", image_name, "-f", sandbox_docker_file, app_dir]
    print(f"Running command: {' '.join(command)}")
    start_time = time.time()
    rc, stdout, stderr = run_docker_subprocess(command, timeout=3600, env=env)
    end_time = time.time()
    print(
        f"Command finished in {end_time - start_time:.8f} seconds with exit code {rc}"
    )
    if rc != 0:
        print(stdout)
        print(stderr)
        raise ValueError(f"Error building docker image: {image_name}")
    return image_name


class Sandbox(abc.ABC):
    def __init__(
        self,
        app_dir: str,
        mounts: list[str] = None,
        network_mode: Literal["none", "bridge", "host"] = "none",
        cap_add: list[str] = None,
        cpu_limit: float = 0.5,
        mem_limit: str = "256m",
        pid_limit: int = 100,
        timeout: int = 30,
        env: dict | None = None,
        sandbox_id: str = None,
    ):
        """
        Base docker-backed sandbox class.

        :param app_dir: The base directory containing the code to run.
        :param mounts: A list of additional mount points in the format "host_path:container_path" (default: None).
        :param network_mode: The Docker network mode to use (default: "none" for no network access).
        :param cap_add: A list of Linux capabilities to add to the container (default: None). Note: cap_drop ALL is used by default to drop all capabilities.
        :param cpu_limit: The CPU limit for the container (default: 0.5 for 50% of a single CPU core).
        :param mem_limit: The memory limit for the container (default: "256m" for 256 MB of RAM).
        :param pid_limit: The maximum number of processes allowed in the container (default: 100).
        :param timeout: The maximum time to allow the command to run in seconds (default: 30).
        """

        if not os.path.exists(app_dir):
            raise ValueError(f"App directory does not exist: {app_dir}")

        if sandbox_id is None:
            sandbox_id = uuid.uuid4().hex

        self.app_dir = app_dir
        self.mounts = mounts
        self.network_mode = network_mode
        self.cap_add = cap_add
        self.cpu_limit = cpu_limit
        self.mem_limit = mem_limit
        self.pid_limit = pid_limit
        self.timeout = timeout
        self.sandbox_id = sandbox_id
        self.env = env

        self.image_name = None

    @abc.abstractmethod
    def dockerlines(self) -> str:
        pass

    @abc.abstractmethod
    def command(self) -> str | list[str]:
        pass

    def build(self) -> None:
        dockerlines = self.dockerlines()
        self.image_name = build_sandbox_image(
            self.sandbox_id, self.app_dir, env=self.env, dockerlines=dockerlines,
        )


    def run(self) -> tuple[int, str, str]:
        container_name = "geenii-sandbox-" + self.sandbox_id
        if self.image_name is None:
            raise ValueError("Sandbox image does not exist")

        command = ["docker", "run", "--rm"]
        command.extend(["--name", container_name])
        # Mount the app directory as read-only and set as working directory
        command.extend(["-v", f"{self.app_dir}:/app:ro"])
        command.extend(["-w", "/app"])

        # Mounts
        if self.mounts:
            for mount in self.mounts:
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
        command.extend(["--network", self.network_mode])

        # Non-root user (nobody)
        command.extend(["--user", "nobody"])

        # Resource limits (optional, but recommended)
        # CPU limit: --cpus="0.5" limits the container to 50% of a single CPU core.
        # Memory limit: --memory="256m" limits the container to 256 MB of RAM.
        # PID limit: --pids-limit=100 limits the container to 100 processes
        if self.cpu_limit is not None:
            command.extend(["--cpus", str(self.cpu_limit)])
        if self.mem_limit is not None:
            command.extend(["--memory", str(self.mem_limit)])
            command.extend(
                ["--memory-swap", str(self.mem_limit)]
            )  # prevent using swap beyond the memory limit
        if self.pid_limit is not None:
            command.extend(
                ["--pids-limit", str(self.pid_limit)]
            )  # prevent fork bombs and excessive process creation

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
        if self.cap_add:
            for cap in self.cap_add:
                command.extend(["--cap-add", cap])
        # no new privileges
        # https://raesene.github.io/blog/2019/06/01/docker-capabilities-and-no-new-privs/
        # command.extend(["--security-opt=no-new-privileges:true"])

        # OOM killer: --oom-kill-disable prevents the container from being killed by the OOM killer, but use with caution as it may lead to resource exhaustion.
        # command.append("--oom-kill-disable")

        # Add gateway host
        command.extend(["--add-host", "host.docker.internal:host-gateway"])

        # Add environment vars
        if self.env is not None:
            for k, v in self.env.items():
                command.extend(["-e", f"{k}={v}"])

        command.append(self.image_name)
        cmd = self.command()
        if isinstance(cmd, str):
            import shlex
            command.extend(shlex.split(cmd))
        else:
            command.extend(cmd)

        print(f"Running command: {' '.join(command)}")
        start_time = time.time()
        result = run_docker_subprocess(command, timeout=self.timeout)
        end_time = time.time()
        print(
            f"Command finished in {end_time - start_time:.8f} seconds with exit code {result[0]}"
        )
        return result


class PythonSandbox(Sandbox):
    def __init__(
        self,
        app_dir: str,
        script_name: str = "main.py",
        script_args: list[str] = None,
        **kwargs,
    ):
        if "sandbox_id" not in kwargs or kwargs["sandbox_id"] is None:
            kwargs["sandbox_id"] = app_dir.replace("\\", "/").replace("/", "-").lower()
        super().__init__(app_dir=app_dir, **kwargs)
        self.script_name = script_name
        self.script_args = script_args

    def dockerlines(self) -> str:
        dockerfile_str = (
            "FROM python:3.13-alpine\n"
            "ENV PYTHONUNBUFFERED=1\n"
            "WORKDIR /app\n"
        )
        if os.path.exists(os.path.join(self.app_dir, "requirements.txt")):
            dockerfile_str += (
                "COPY ./requirements.txt ./\n"
                "RUN pip3 install -r ./requirements.txt\n"
            )
        if os.path.exists(os.path.join(self.app_dir, "pyproject.toml")):
            dockerfile_str += (
                "COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/\n"
                "COPY ./pyproject.toml ./uv.lock ./\n"
                "RUN uv sync --no-cache-dir --frozen --no-install-project --no-dev\n"
            )
        return dockerfile_str

    def command(self) -> list[str]:
        cmd = ["python3", self.script_name]
        if self.script_args:
            cmd.extend(self.script_args)
        return cmd


class BashSandbox(Sandbox):
    def __init__(
        self,
        app_dir: str,
        shell_command: str | None = None,
        script_name: str | None = None,
        script_args: list[str] = None,
        **kwargs,
    ):
        if shell_command and script_name:
            raise ValueError("shell_command and script_name are mutually exclusive")
        if not shell_command and not script_name:
            raise ValueError("Either shell_command or script_name must be provided")
        super().__init__(app_dir=app_dir, **kwargs)
        self._shell_command = shell_command
        self._script_name = script_name
        self._script_args = script_args

    def dockerlines(self) -> str:
        return (
            "FROM bash:latest\n"
            "WORKDIR /app\n"
        )

    def command(self) -> list[str]:
        import shlex
        if self._shell_command:
            return ["bash", "-c", self._shell_command]
        cmd = ["bash", self._script_name]
        if self._script_args:
            cmd.extend(self._script_args)
        return cmd


class NodeJsSandbox(Sandbox):
    def __init__(
        self,
        app_dir: str,
        script_name: str = "index.js",
        script_args: list[str] = None,
        **kwargs,
    ):
        super().__init__(app_dir=app_dir, **kwargs)
        self.script_name = script_name
        self.script_args = script_args

    def dockerlines(self) -> str:
        dockerfile_str = (
            "FROM node:22-alpine\n"
            "WORKDIR /app\n"
        )
        if os.path.exists(os.path.join(self.app_dir, "package.json")):
            dockerfile_str += (
                "COPY ./package.json ./package-lock.json* ./\n"
                "RUN npm ci --omit=dev 2>/dev/null || npm install --omit=dev\n"
            )
        return dockerfile_str

    def command(self) -> list[str]:
        cmd = ["node", self.script_name]
        if self.script_args:
            cmd.extend(self.script_args)
        return cmd