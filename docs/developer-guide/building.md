# Building

This guide covers building Geenii from source: running the development
environment, producing distributable artifacts, and building the Docker image.

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (package manager and task runner)
- [Docker](https://www.docker.com/) (for image builds)
- [PyInstaller](https://pyinstaller.org/) (bundled as a dev dependency)

## Development setup

```bash
git clone https://github.com/fm-labs/geenii.git
cd geenii
uv sync --group dev
```

This installs all runtime and dev dependencies (pytest, ruff, pyinstaller,
nuitka, testcontainers) into a virtual environment managed by uv.

Run the CLI from source:

```bash
uv run geenii --version
uv run geenii info
```

## Linting

The project uses [ruff](https://docs.astral.sh/ruff/) for linting:

```bash
uv run ruff check src/
```

## Testing

Tests use pytest. The `src/` directory is on the Python path via
`tool.pytest.ini_options` in `pyproject.toml`.

```bash
uv run pytest tests/ -v
```

Some tests use [testcontainers](https://testcontainers-python.readthedocs.io/)
and require a running Docker daemon.

## Build targets

### Python wheel

Build a standard wheel with hatchling:

```bash
uv build --wheel
```

Output lands in `dist/`. The wheel is a pure-Python package installable with
`pip install dist/geenii-*.whl`.

The build script `build_wheel.sh` wraps this with cleanup.

### PyInstaller binary (one-dir)

Produces a self-contained directory with a `geenii` executable and all
dependencies bundled. This is the format used inside the Docker image.

```bash
./build_od.sh
```

Output: `dist/geenii/` (directory containing the executable and supporting
files).

The `hooks/` directory contains a PyInstaller hook
(`hook-geenii.provider.py`) for collecting provider subpackages. The
`--copy-metadata fastmcp` flag ensures fastmcp's package metadata is
included.

### PyInstaller binary (one-file)

Produces a single self-contained executable:

```bash
./build_bin.sh
```

Output: `dist/geenii` (single file). Larger startup time than one-dir but
simpler to distribute.

### Build scripts summary

| Script | Method | Output |
|---|---|---|
| `build_wheel.sh` | `uv build --wheel` | `dist/geenii-*.whl` |
| `build_od.sh` | PyInstaller `--onedir` | `dist/geenii/` (directory) |
| `build_bin.sh` | PyInstaller `--onefile` | `dist/geenii` (single binary) |
| `build_image.sh` | `docker build` | `geenii:latest` image |

## Docker image

### Building locally

```bash
./build_image.sh
```

This runs `docker build` using the project `Dockerfile` and tags the image as
`geenii:latest`.

### Dockerfile overview

The image is a two-stage build:

**Stage 1 — builder** (`python:3.14-alpine`):
1. Installs build dependencies (gcc, libffi-dev, etc.) and uv.
2. Copies `pyproject.toml` + `uv.lock` and runs `uv sync --frozen` to
   install Python dependencies.
3. Copies the source and runs `build_od.sh` (PyInstaller one-dir build).

**Stage 2 — runtime** (`python:3.14-alpine`):
1. Installs runtime system packages: bash, curl, git, Node.js, npm/pnpm,
   docker-cli, openssl, openssh-client.
2. Creates a non-root `geenii` user (UID/GID 33311).
3. Copies the PyInstaller output from the builder stage to `/opt/geenii/`
   and symlinks `/usr/bin/geenii`.
4. Sets the entrypoint to `container/entrypoint.sh`, which delegates to
   `geenii`.

```
WORKDIR  /workspace
USER     geenii
ENTRYPOINT ["/usr/bin/entrypoint"]
CMD      ["--help"]
```

### Running the image

```bash
docker run --rm geenii:latest --version
docker run --rm -v $(pwd)/.geenii:/.geenii geenii:latest agent "Hello"
```

See the [Docker user guide](../user-guide/docker.md) for volume mounts,
data persistence, and production usage.

## CI/CD

GitHub Actions workflows in `.github/workflows/`:

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | Push/PR to `main` | Lint with ruff, run pytest on Python 3.13 + 3.14 |
| `publish.yml` | Tag `v*` | Build PyInstaller binaries for linux/amd64, linux/arm64, darwin/amd64, darwin/arm64; create GitHub release with tarballs + checksums |
| `publish_image_multiarch.yml` | Tag `v*` | Build Docker images for linux/amd64 + linux/arm64, push to Docker Hub, create multi-arch manifest, smoke test |

### Release process

1. Bump version in `pyproject.toml`.
2. Commit and push to `main`.
3. Tag the commit: `git tag v0.3.3 && git push --tags`.
4. CI builds binaries and Docker images, creates a GitHub release, and pushes
   the image to Docker Hub as both `<tag>` and `latest`.

## Project entry points

Defined in `pyproject.toml` under `[project.scripts]`:

| Console script | Module | Purpose |
|---|---|---|
| `geenii` | `geenii.cli.main:main` | Main CLI |
| `geenii-scheduler` | `geenii.scheduler:main` | Standalone scheduler process |
