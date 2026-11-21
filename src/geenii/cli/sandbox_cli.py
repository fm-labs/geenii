import hashlib
import os
import re
import shutil
import subprocess
import sys

import click

from geenii import config
from geenii.cli.click_helper import click_error, click_success
from geenii.sandbox import SANDBOX_IMAGE_PREFIX, BashSandbox, NodeJsSandbox, PythonSandbox

RUNTIMES = ("python", "bash", "node")
DEFAULT_SCRIPTS = {"python": "main.py", "node": "index.js"}
ENV_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
# A sandbox id becomes part of a docker image name (and a cache directory name)
SANDBOX_ID_RE = re.compile(r"[a-z0-9]+(?:[._-][a-z0-9]+)*")


def default_sandbox_id(runtime: str, app_dir: str) -> str:
    """`<runtime>-<dir name>-<hash>`: stable per runtime and directory, so the image is reused"""
    app_dir = os.path.realpath(app_dir)
    name = re.sub(r"[^a-z0-9]+", "-", os.path.basename(app_dir).lower()).strip("-") or "app"
    digest = hashlib.sha256(app_dir.encode()).hexdigest()[:8]
    return f"{runtime}-{name}-{digest}"


def _sandboxes_dir() -> str:
    return os.path.join(config.GEENII_CACHE_DIR, "sandboxes")


def _parse_env(values: tuple[str, ...]) -> dict[str, str]:
    env = {}
    for item in values:
        key, sep, value = item.partition("=")
        if not ENV_NAME_RE.fullmatch(key):
            raise click.BadParameter(f"invalid variable name: {key!r}", param_hint="--env")
        if not sep:
            # `-e NAME`: take the value from the current environment, like docker
            if key not in os.environ:
                raise click.BadParameter(f"{key} is not set in the environment", param_hint="--env")
            value = os.environ[key]
        env[key] = value
    return env


def _docker(*args: str) -> subprocess.CompletedProcess:
    if shutil.which("docker") is None:
        raise click.ClickException("docker not found: the sandbox needs Docker")
    return subprocess.run(["docker", *args], capture_output=True, text=True, check=False)


def _sandbox_images() -> list[dict[str, str]]:
    result = _docker("images", "--filter", f"reference={SANDBOX_IMAGE_PREFIX}*", "--format", "{{.Repository}}\t{{.Size}}\t{{.CreatedSince}}")
    if result.returncode != 0:
        raise click.ClickException(f"docker images failed: {result.stderr.strip()}")
    images = []
    for line in result.stdout.splitlines():
        repo, size, created = (line.split("\t") + ["", ""])[:3]
        images.append({"id": repo.removeprefix(SANDBOX_IMAGE_PREFIX), "image": repo, "size": size, "created": created})
    return images


@click.group()
def sandbox():
    """Run code in a Docker sandbox and manage sandbox images."""


@sandbox.command("run", context_settings={"ignore_unknown_options": True})
@click.argument("runtime", type=click.Choice(RUNTIMES))
@click.argument("app_dir", type=click.Path(exists=True, file_okay=False))
@click.argument("script", required=False)
@click.argument("script_args", nargs=-1, type=click.UNPROCESSED)
@click.option("--command", "-c", "shell_command", help="bash only: run this shell command instead of a script.")
@click.option(
    "--network", type=click.Choice(["none", "bridge", "host"]), default="none", show_default=True, help="Docker network mode."
)
@click.option("--cpus", type=float, default=0.5, show_default=True, help="CPU limit (cores).")
@click.option("--memory", default="256m", show_default=True, help="Memory limit (no swap beyond it).")
@click.option("--pids", type=int, default=100, show_default=True, help="Maximum number of processes.")
@click.option("--timeout", "-t", type=int, default=30, show_default=True, help="Seconds before the run is aborted.")
@click.option("--env", "-e", "env_items", multiple=True, help="KEY=VALUE, or KEY to pass it from the current env (repeatable).")
@click.option("--mount", "-m", "mounts", multiple=True, help="Extra docker volume, HOST:CONTAINER[:ro] (repeatable).")
@click.option("--cap-add", "cap_add", multiple=True, help="Linux capability to add back (all are dropped; repeatable).")
@click.option("--id", "sandbox_id", help="Sandbox id, names the image (default: <runtime>-<dir>-<hash>).")
def run_sandbox(
    runtime, app_dir, script, script_args, shell_command, network, cpus, memory, pids, timeout, env_items, mounts, cap_add, sandbox_id
):
    """Run SCRIPT from APP_DIR in a sandbox container of RUNTIME.

    Builds the sandbox image first (dependencies from requirements.txt / pyproject.toml + uv.lock
    for python, package.json for node; docker caches the layers), then runs SCRIPT with
    SCRIPT_ARGS. APP_DIR is mounted read-only at /app. Exits with the script's exit code.

    \b
    Examples:
      geenii sandbox run python ./my-skill scripts/fetch.py --format json
      geenii sandbox run bash . -c 'ls -la /app' --network none
      geenii sandbox run python . -e API_KEY --network bridge -t 120
    """
    app_dir = os.path.realpath(app_dir)
    if shell_command and runtime != "bash":
        raise click.UsageError("--command is only supported for the bash runtime")
    if shell_command and (script or script_args):
        raise click.UsageError("--command and SCRIPT are mutually exclusive")
    script = script or DEFAULT_SCRIPTS.get(runtime)
    if not shell_command:
        if script is None:
            raise click.UsageError("bash needs a SCRIPT or --command")
        if not os.path.isfile(os.path.join(app_dir, script)):
            raise click.UsageError(f"Script not found in {app_dir}: {script}")
    sandbox_id = sandbox_id or default_sandbox_id(runtime, app_dir)
    if not SANDBOX_ID_RE.fullmatch(sandbox_id):
        raise click.BadParameter("lowercase letters, digits and single . _ - separators only", param_hint="--id")
    if shutil.which("docker") is None:
        raise click.ClickException("docker not found: the sandbox needs Docker")

    options = dict(
        mounts=list(mounts) or None,
        network_mode=network,
        cap_add=list(cap_add) or None,
        cpu_limit=cpus,
        mem_limit=memory,
        pid_limit=pids,
        timeout=timeout,
        env=_parse_env(env_items) or None,
        sandbox_id=sandbox_id,
    )
    args = list(script_args) or None
    if runtime == "python":
        box = PythonSandbox(app_dir, script_name=script, script_args=args, **options)
    elif runtime == "node":
        box = NodeJsSandbox(app_dir, script_name=script, script_args=args, **options)
    elif shell_command:
        box = BashSandbox(app_dir, shell_command=shell_command, **options)
    else:
        box = BashSandbox(app_dir, script_name=script, script_args=args, **options)

    click.echo(f"Building sandbox image {SANDBOX_IMAGE_PREFIX}{sandbox_id} ...", err=True)
    try:
        box.build()
    except ValueError as e:
        raise click.ClickException(str(e)) from e
    rc, stdout, stderr = box.run()
    if stdout:
        click.echo(stdout, nl=False)
    if stderr:
        click.echo(stderr, nl=not stderr.endswith("\n"), err=True)
    sys.exit(rc if 0 <= rc <= 255 else 1)


@sandbox.command("list")
def list_sandboxes():
    """List the sandbox images."""
    images = _sandbox_images()
    if not images:
        click.echo("No sandbox images.")
        return
    width = max(len(i["id"]) for i in images)
    click.echo(f"{'ID':<{width}}  {'SIZE':>8}  CREATED")
    for image in images:
        click.echo(f"{image['id']:<{width}}  {image['size']:>8}  {image['created']}")


@sandbox.command("rm")
@click.argument("sandbox_ids", nargs=-1)
@click.option("--all", "remove_all", is_flag=True, help="Remove all sandbox images.")
def remove_sandboxes(sandbox_ids, remove_all):
    """Remove sandbox images (and their cached Dockerfiles) by id."""
    if remove_all == bool(sandbox_ids):
        raise click.UsageError("Give one or more sandbox ids, or --all")
    if remove_all:
        sandbox_ids = tuple(i["id"] for i in _sandbox_images())
        if not sandbox_ids:
            click.echo("No sandbox images.")
            return
    failed = False
    for sandbox_id in sandbox_ids:
        if not SANDBOX_ID_RE.fullmatch(sandbox_id):
            click_error(f"Invalid sandbox id: {sandbox_id}")
            failed = True
            continue
        result = _docker("rmi", f"{SANDBOX_IMAGE_PREFIX}{sandbox_id}")
        shutil.rmtree(os.path.join(_sandboxes_dir(), sandbox_id), ignore_errors=True)
        if result.returncode != 0:
            click_error(f"{sandbox_id}: {result.stderr.strip()}")
            failed = True
        else:
            click_success(f"Removed {sandbox_id}")
    if failed:
        sys.exit(1)
