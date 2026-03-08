import logging
import os
import shlex
import subprocess

logger = logging.getLogger(__name__)

def cleanup(*args):
    """Perform maintenance tasks"""
    logger.info("Performing cleanup tasks...")


def run_agent(params: list[str], env: dict | None = None) -> None:
    """Run the main loop for the agent"""
    logger.info(f"run_agent {params} env={env}")


def run_proc(params: list[str], env: dict | None = None) -> None:
    """Run a subprocess command"""
    logger.info(f"run_proc {params} env={env}")

    # quick and dirty hack to allow passing the command as a single string or as a list of strings
    cmd = shlex.split(params[0]) + params[1:]
    logger.info(f"Running subprocess with command: {cmd}")

    _env = os.environ.copy()
    if env:
        _env.update(env)

    result = subprocess.run(cmd, capture_output=True, text=True, env=_env)
    logger.info(f"Subprocess finished with return code {result.returncode}")
    logger.info(f"Subprocess stdout: {result.stdout}")
    logger.info(f"Subprocess stderr: {result.stderr}")
