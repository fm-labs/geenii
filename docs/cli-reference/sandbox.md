# geenii sandbox

Run a script or shell command in a short-lived, locked-down Docker container,
and manage the sandbox images. This is the CLI for the sandbox described in
[Sandbox](../developer-guide/sandbox.md). Docker must be installed and its
daemon reachable; the geenii daemon is not needed.

## sandbox run

```
geenii sandbox run [OPTIONS] {python|bash|node} APP_DIR [SCRIPT] [SCRIPT_ARGS]...
```

Builds the sandbox image for APP_DIR, then runs SCRIPT (with SCRIPT_ARGS) in a
container of it. Prints the script's stdout and stderr when it finishes and
exits with its exit code: 1 if the run timed out or docker failed, 2 for
invalid arguments.

| Runtime | Base image | Default SCRIPT | Dependencies baked into the image |
|---|---|---|---|
| `python` | `python:3.14-alpine` | `main.py` | `requirements.txt` (pip), `pyproject.toml` + `uv.lock` (uv) |
| `bash` | `bash:latest` | *(none: give SCRIPT or `-c`)* | none |
| `node` | `node:22-alpine` | `index.js` | `package.json` (`npm ci`, or `npm install`) |

The image is rebuilt on every run, and Docker's layer cache keeps that fast
when nothing changed. Its Dockerfile is kept in
`$GEENII_CACHE_DIR/sandboxes/<id>/`.

| Option | Short | Default | Description |
|---|---|---|---|
| `--command` | `-c` | | bash only: run this shell command instead of SCRIPT |
| `--network` | | `none` | Docker network mode: `none`, `bridge` (outbound access) or `host` |
| `--cpus` | | `0.5` | CPU limit in cores |
| `--memory` | | `256m` | Memory limit; swap is capped at the same value |
| `--pids` | | `100` | Maximum number of processes |
| `--timeout` | `-t` | `30` | Seconds before the run is aborted and the container removed |
| `--env` | `-e` | | `KEY=VALUE`, or `KEY` to pass its value from the current environment (repeatable) |
| `--mount` | `-m` | | Extra docker volume, `HOST:CONTAINER[:ro]` (repeatable) |
| `--cap-add` | | | Linux capability to add back; all are dropped (repeatable) |
| `--id` | | `<runtime>-<dir name>-<hash>` | Sandbox id: names the image (`geenii-sandbox-<id>`) and container |

Every run uses the sandbox's hardening, which these options can't turn off:

- APP_DIR is mounted read-only at `/app` (the working directory).
- The root filesystem is read-only; `/tmp` is a private tmpfs.
- The container runs as user `nobody` with all capabilities dropped, except
  the ones given with `--cap-add`.
- The container is removed when the run ends (`--rm`).

`--env` values reach the container through docker's environment, not its
arguments, so they don't show in the process list or the debug log.

Options can go before or after SCRIPT. Options that geenii doesn't know pass
through to the script. Use `--` before script arguments that look like
geenii options, such as `-t` or `-e`:

```bash
geenii sandbox run python ./my-skill scripts/fetch.py --format json
geenii sandbox run python ./my-skill main.py -e API_KEY --network bridge -t 120 -- -t 5
geenii sandbox run bash . -c 'ls -la /app'
geenii sandbox run node ./tool index.js --memory 512m
```

Runs with the same id share one container name, so they can't run at the
same time; give one of them another `--id`.

## sandbox list

```
geenii sandbox list
```

Lists the sandbox images (`geenii-sandbox-*`) with their id, size and age.

## sandbox rm

```
geenii sandbox rm ID... | --all
```

Removes sandbox images by id (as `list` shows it), or all of them with
`--all`, along with their cached Dockerfiles. Exits with 1 if any image
couldn't be removed.
