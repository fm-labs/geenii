# Sandbox

The sandbox provides Docker-based isolation for executing untrusted code
generated or requested by agents. Instead of running commands directly on the
host (as `ComputerTool` does today), sandboxed execution confines code inside a
short-lived container with restricted capabilities, resource limits, and
optional network isolation.

## Motivation

Agents equipped with code-execution tools (`bash`, `python`) can run arbitrary
commands on the host machine. The HITL controller gates execution with an
approval step, but in autonomous or scheduled runs no human is present. The
sandbox provides a defence-in-depth layer: even if a tool call is approved
(or auto-approved), the code runs inside a container that limits what damage
it can do.

## How it works

`geenii/sandbox.py` exposes two main entry points:

1. **`build_sandbox_container()`** — generates a Dockerfile on the fly for the
   chosen runtime, builds a Docker image, and returns the image name.
2. **`run_docker_sandbox_python()`** — builds the container (if needed), then
   runs a script inside it with the full set of security constraints applied.

The lifecycle of a sandboxed execution is:

```
app_dir (host)
  │
  ├─ build_sandbox_container()
  │    ├─ generate Dockerfile for runtime (python / node / bash)
  │    ├─ install deps (requirements.txt or pyproject.toml via uv)
  │    └─ docker build → image "geenii-sandbox-<runtime>-<id>"
  │
  └─ run_docker_sandbox_python()
       ├─ docker run --rm  (one-shot, container removed after exit)
       │    ├─ mount app_dir as /app:ro  (read-only)
       │    ├─ mount tmpfs at /tmp       (writable scratch space)
       │    ├─ --read-only root filesystem
       │    ├─ --user nobody
       │    ├─ --network <mode>
       │    ├─ resource limits (cpu, memory, pids)
       │    ├─ --cap-drop ALL
       │    └─ python3 <script> [args...]
       └─ returns (exit_code, stdout, stderr)
```

Dockerfiles are cached in `$GEENII_CACHE_DIR/sandboxes/`.

## Security model

Every container is launched with the following hardening by default:

| Control | Default | Purpose |
|---|---|---|
| **Filesystem** | `--read-only` root; app mounted `:ro`; tmpfs at `/tmp` | Prevent persistent writes to the host or the container image |
| **User** | `--user nobody` | No root inside the container |
| **Capabilities** | `--cap-drop ALL` | Drop all Linux capabilities; add back selectively via `cap_add` |
| **Network** | `--network none` | No network access; override with `bridge` or `host` when needed |
| **CPU** | `--cpus 0.5` | Limit to 50 % of one core |
| **Memory** | `--memory 256m`, `--memory-swap 256m` | Hard memory cap, no swap overshoot |
| **PIDs** | `--pids-limit 100` | Prevent fork bombs |
| **Timeout** | `subprocess` timeout (default 30 s) | Kill the container if it runs too long |

These defaults are deliberately restrictive. Callers can relax individual
constraints through function parameters when the use case demands it (e.g.
`network_mode="bridge"` for a skill that needs to call an API).

## Supported runtimes

`build_sandbox_container()` accepts a `runtime` argument:

| Runtime | Base image | Dependency handling |
|---|---|---|
| `python` | `python:3.13-alpine` | `requirements.txt` via pip; `pyproject.toml` + `uv.lock` via uv |
| `node` | `node:latest` | None (npm install not yet wired) |
| `bash` | `bash:latest` | None |

## API

### `build_sandbox_container`

```python
build_sandbox_container(
    sandbox_id: str,       # unique identifier for caching the image
    app_dir: str,          # host directory containing the code + deps
    env: dict | None,      # extra env vars for the build
    runtime: str = "bash", # "python", "node", or "bash"
) -> str                   # returns the Docker image name
```

### `run_docker_sandbox_python`

```python
run_docker_sandbox_python(
    app_dir: str,                       # host directory with the script
    script_name: str = "main.py",       # script to execute
    script_args: list[str] = None,      # arguments passed to the script
    mounts: list[str] = None,           # additional "host:container" mounts
    network_mode: "none"|"bridge"|"host" = "none",
    cap_add: list[str] = None,          # capabilities to re-add
    cpu_limit: float = 0.5,
    mem_limit: str = "256m",
    pid_limit: int = 100,
    timeout: int = 30,                  # seconds
    env: dict | None = None,            # env vars passed into the container
    sandbox_id: str = None,             # defaults to a slug of app_dir
) -> tuple[int, str, str]              # (exit_code, stdout, stderr)
```

### `run_docker_subprocess`

Low-level helper that runs any command list via `subprocess.run` with a
timeout. Used internally by the build and run functions.

```python
run_docker_subprocess(
    command: list[str],
    timeout: int = 30,
    env: dict | None = None,
) -> tuple[int, str, str]
```

## Agent integration — `SandboxTool`

`geenii/tool/sandbox.py` provides `SandboxTool`, a `Tool` subclass that wraps
the sandbox module behind the standard tool interface. Two instances are
registered by `init_builtin_tools()`:

| Tool name | Runtime | Description |
|---|---|---|
| `sandbox_python` | `python` | Run a Python command in a sandboxed container |
| `sandbox_bash` | `bash` | Run a shell command in a sandboxed container |

These sit alongside the unsandboxed `bash` and `python` `ComputerTool`s. An
agent's `tools` list controls which ones are visible to the model — use
`sandbox_python` instead of (or in addition to) `python` to route execution
through Docker.

### How it works

When the model invokes `sandbox_python` (or `sandbox_bash`):

1. `SandboxTool.invoke()` reads `SKILL_DIR` from the tool env (set automatically
   by `ToolCallTask` when a skill is selected).
2. It calls `build_sandbox_container()` with the skill directory as the app dir,
   installing any `requirements.txt` or `pyproject.toml` dependencies.
3. It runs the command inside the container with all the security controls from
   the table above applied.
4. stdout is returned to the model on success; on failure, the exit code +
   stderr are returned.

If Docker is not installed, `invoke()` raises `RuntimeError` immediately. If
no skill is selected (no `SKILL_DIR` in env), it raises `ValueError` — the
sandbox needs a directory to mount.

### Agent spec example

```markdown
---
name: data-fetcher
model: ollama:qwen3:8b
skills:
  - my-data-skill
tools:
  - sandbox_python
  - display_desktop_notification
---

Use the sandbox_python tool to run scripts from the skill directory.
```

### `SandboxTool` constructor

```python
SandboxTool(
    name: str,
    description: str = "",
    parameters: dict | None = None,
    runtime: "python" | "node" | "bash" = "bash",
    network_mode: "none" | "bridge" | "host" = "none",
    cpu_limit: float = 0.5,
    mem_limit: str = "256m",
    pid_limit: int = 100,
    timeout: int = 30,
)
```

Custom instances with relaxed limits can be registered directly:

```python
from geenii.tool.sandbox import SandboxTool

registry.register(SandboxTool(
    name="sandbox_python_network",
    description="Python sandbox with network access.",
    parameters={...},
    runtime="python",
    network_mode="bridge",
    timeout=120,
    mem_limit="512m",
))
```

## Standalone use

The low-level `run_docker_sandbox_python` function can be used outside the
agent pipeline:

```python
from geenii.sandbox import run_docker_sandbox_python

rc, stdout, stderr = run_docker_sandbox_python(
    app_dir="/path/to/my-skill",
    script_name="scripts/fetch_data.py",
    script_args=["--format", "json"],
    network_mode="bridge",
    timeout=60,
    env={"API_KEY": "..."},
    sandbox_id="my-skill",
)
print(stdout if rc == 0 else stderr)
```

## Future work

- **Configuration via agent spec / user settings** — declare sandbox mode and
  per-tool overrides for network, resource limits, etc.
- **Node runtime runner** — `build_sandbox_container` supports Node, but there
  is no `run_docker_sandbox_node` yet.
- **Image caching** — skip rebuild when the Dockerfile and deps haven't changed.

## Test fixtures

`data/sandbox/` contains two test scripts used during development:

- `main.py` — prints user/group/env info and simulates a long-running process
  (useful for verifying UID mapping, capability dropping, and timeouts).
- `hello.py` — minimal module import test.
