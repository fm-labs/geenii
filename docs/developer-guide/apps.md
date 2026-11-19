# Apps (GeeApps)

A GeeApp is a sandboxed micro-application managed by geenii. Four app types
are supported:

| Type         | Runtime               | Default entry point                  | Launch command                  |
|--------------|-----------------------|--------------------------------------|---------------------------------|
| `statichtml` | Python `http.server`  | `index.html`                         | `python3 -m http.server $PORT`  |
| `python`     | Python                | `main.py`, `app.py` or `server.py`   | `<python> $main`                |
| `node`       | Node.js               | `index.js`                           | `npm start` or `node $main`     |
| `binary`     | None (compiled)       | *(must be set)*                      | `./$main`                       |

## Concepts

A GeeApp is a thin wrapper around a directory of files plus a manifest that
tells geenii how to run them. The registry discovers apps and reads (or
infers) their manifests. The [geenii daemon](processes.md#the-geenii-daemon-geeniidaemon)
holds the registry and runs apps as supervisor services; the `geenii apps`
CLI talks to it.

Port allocation is automatic (a random free port from 42000-44000) but can be
overridden per app via the manifest `port` field or the `--port` CLI flag.

## App directory layout

```
apps/
└── my-app/
    ├── manifest.json       # metadata + launch config
    ├── index.html          # entry point (statichtml)
    ├── script.js           # optional
    └── styles.css          # optional
```

## App discovery paths

`config.apps_dirs()` lists the standard app directories:

1. `~/.geenii/apps` — user-global apps
2. `$GEENII_WORKING_DIR/.geenii/apps` — project apps

The daemon is one per user, so its registry starts with `~/.geenii/apps`
only. Clients add project directories through the `dirs` param of the
`apps.*` methods: the CLI sends the directories of `config.apps_dirs()` that
exist, plus `--dir`. When two directories contain an app with the same name,
the later one wins. Directories starting with `.` and apps with an invalid
manifest are skipped (the latter with an error in the daemon log).

## Manifest (`manifest.json`)

```json
{
  "name": "my-app",
  "type": "statichtml",
  "title": "My App",
  "description": "A small demo app",
  "author": "phil",
  "version": "1.0.0",
  "main": "index.html",
  "port": 9100,
  "env": {},
  "sandbox": false
}
```

Only `name` is required. All other fields have sensible defaults:

| Field         | Default     | Description                                          |
|---------------|-------------|------------------------------------------------------|
| `name`        | *(required)* | Unique app identifier                               |
| `type`        | `statichtml` | One of `statichtml`, `python`, `node`, `binary`     |
| `title`       | `null`      | Human-readable display name                          |
| `description` | `null`      | Short description                                    |
| `author`      | `null`      | Author name                                          |
| `version`     | `null`      | Semver version string                                |
| `main`        | `null`      | Entry point file (auto-detected per type if omitted) |
| `port`        | `null`      | Preferred port (auto-allocated if omitted)           |
| `env`         | `{}`        | Environment variables passed to the process          |
| `sandbox`     | `false`     | Run inside Docker sandbox (not yet wired)            |

Extra fields are allowed — the manifest uses `extra = "allow"` so
app-specific metadata won't break validation.

### Auto-inference

If no `manifest.json` exists, the registry infers the type from directory
contents:

1. `package.json` present → `node`
2. `pyproject.toml`, `requirements.txt`, `main.py`, `app.py` or `server.py`
   present → `python`
3. `index.html` present → `statichtml`
4. Executable binary named after the directory → `binary`
5. Fallback → `statichtml`

Use `geenii apps init <name>` or `geenii apps init-all` to write inferred
manifests to disk.

## Source code

### `src/geenii/apps.py`

**Enums:**

- `AppType` — `statichtml`, `python`, `node`, `binary`
- `AppStatus` — `stopped`, `starting`, `running`, `error`

**Models:**

- `GeeAppManifest` — Pydantic model for `manifest.json`
- `GeeApp` — wraps a manifest with filesystem path, trusted flag and
  assigned `port`. `info()` returns its static info. `to_service_config()`
  and `service_name` describe the app as a supervisor service (see
  [Running as a background service](#running-as-a-background-service)).
  It has no process lifecycle of its own: the supervisor runs it

**Registry:**

`AppRegistry(dirs=None)` — discovery and registration:

- `add_dir(path)` / `dirs` — the directories to scan, in order
- `reload()` — rescan all directories; returns `{"added", "removed"}`.
  Ports assigned to apps that still exist are kept. The new app set is built
  aside and swapped in, so concurrent readers never see a partial one
- `load_from_directory(path, trusted=False)` — scan one directory, read or
  infer manifests, register all apps
- `assign_port(name, port=None)` — pin the app's port: the given one, else
  its current or manifest port, else a random free port from 42000-44000 (`APP_PORT_RANGE`) that no
  other app uses
- `get(name)` / `require(name)` / `list()` / `names()` — lookups (`require`
  raises `KeyError`)
- `register(app)` / `unregister(name)` — manual registration

**Helpers:**

- `read_manifest(app_dir)` — read and validate `manifest.json`, returns
  `None` if missing
- `infer_manifest(app_dir, name)` — auto-detect type from directory contents
- `write_manifest(app_dir, manifest)` — write `manifest.json` to disk

### `src/geenii/daemon/host.py`

`ProcessHost` holds the daemon's `AppRegistry` (`host.apps`) and registers
the `apps.*` RPC methods. See [The daemon](#the-daemon).

### `src/geenii/cli/apps_cli.py`

Click command group registered as `geenii apps`. Every command except
`init`/`init-all` calls the daemon through `DaemonClient`. See
[CLI reference](../cli-reference/apps.md) for full usage.

## Launch behaviour by type

The port is resolved in this order: the port passed to
`to_service_config()`, the port assigned by `AppRegistry.assign_port()`, the
manifest `port`. If a port is known, it is passed to every app type as the `PORT`
environment variable. The manifest `env` is passed as well.

### `statichtml`

Serves the app directory with Python's built-in `http.server`. The entry
point (`main`) defaults to `index.html`. The server runs on the resolved
port (8000 if none is set) with `cwd` set to the app directory, so all
relative paths resolve correctly. It binds to all network interfaces.

### `python`

Runs `<python> <main>` in the app directory. `main` defaults to the first
of `main.py`, `app.py` or `server.py` that exists (else `main.py`). The
interpreter is the app's own virtualenv (`.venv/` or `venv/`) if present,
otherwise `python3` from `PATH`. Dependencies are not installed
automatically. `PYTHONUNBUFFERED=1` is set (unless the manifest `env`
overrides it) so output reaches the logs line by line.

### `node`

If `package.json` exists, runs `npm start`. Otherwise runs `node <main>`
where `main` defaults to `index.js` (or `server.js` if present). The `PORT`
environment variable is set if a port is assigned.

### `binary`

Executes the binary at `<app_dir>/<main>` directly. The `main` field is
required — inference looks for an executable file named after the app
directory. No runtime needed.

## Running as a background service

`GeeApp.to_service_config(port=None, restart=True)` returns a
`geenii.supervisor.ServiceConfig`, so an app can be run by the process
supervisor instead of as a bare subprocess:

```python
app = registry.get("my-app")
config = app.to_service_config(port=9100)
# ServiceConfig(name="app-my-app", cmd=["python3", "-m", "http.server", "9100"],
#               env={"PORT": "9100"}, cwd="/home/me/.geenii/apps/my-app", restart=True)
```

- `name` is `app.service_name` (`app-<name>`); the prefix keeps app
  services apart from other services in `services.json`
- `cmd` is the launch command described above
- `env` holds only the app's own variables (manifest `env`, `PORT`,
  `PYTHONUNBUFFERED` for python apps); the supervisor merges them into its
  own environment when it spawns the process
- `cwd` is the app directory

`ServiceConfig.to_proc_config()` turns it into the supervisor's runtime
`ProcConfig` (taking `cmd` and `cwd` as they are, unlike `services.json`
entries, which get `$VAR` and `~` expanded). The result can also be
serialized into a `services.json` entry with `config.model_dump()`.

## The daemon

The daemon's `ProcessHost` owns an `AppRegistry` and scans it at start.
Apps run as supervisor services:

- `apps.start` assigns the app's port, builds `to_service_config()` and
  passes it to `Supervisor.ensure()`. The supervisor restarts the app when it
  exits and keeps its output (`apps.logs`)
- `apps.stop` calls `Supervisor.stop_process()`, which removes the service
- `apps.restart` rebuilds the service config from the current manifest, then
  restarts it
- the app status comes from the supervisor status of `app-<name>`: `running`
  while a process runs, `error` once it has failed (restarting or given up),
  `starting` while the supervisor is about to (re)spawn it, else `stopped`
- stopping the daemon stops all apps with the other supervised processes

Apps are not started automatically when the daemon starts. An app removed
from disk while running keeps running; stop it with
`geenii supervisor stop app-<name>`.

For the method list and params, see the
[wire protocol](processes.md#wire-protocol).

## HTTP API

`src/geenii/server/apps_routes.py` mounts `/api/v1/apps` on top of the
daemon's `apps.*` methods. Each call sends the server's app directories
(`config.apps_dirs()`, the ones that exist) as `dirs`, so the daemon also
knows the server's project apps. Responses use the app info dict of the
[wire protocol](processes.md#wire-protocol).

| Method & path | Returns |
|---|---|
| `GET /apps/` | `{"apps": [...], "daemon": {"running": bool}}`. Without a daemon, the apps on disk with `status: null` |
| `GET /apps/{name}` | App info (`status: null` without a daemon). 404 unknown |
| `POST /apps/{name}/start` | Optional body `{"port": int}`. App info. 409 already started |
| `POST /apps/{name}/stop` | App info. 409 not started |
| `POST /apps/{name}/restart` | Optional body `{"port": int}`; keeps the port if omitted. App info |
| `GET /apps/{name}/logs?tail=200` | `{"name", "lines"}`; `lines` is empty if the app never ran |
| `POST /apps/reload` | `{"added", "removed", "dirs"}` |

Every route except the two reads returns 409 when the daemon isn't running,
and 503 when it can't be reached. Unknown apps are 404, and invalid params
are 400 or 422.

## Current status

| Area               | Status           | Notes                                             |
|--------------------|------------------|---------------------------------------------------|
| Models & registry  | Done             | `GeeAppManifest`, `GeeApp`, `AppRegistry`         |
| CLI commands        | Done             | `list`, `info`, `start`, `stop`, `restart`, `logs`, `reload`, `init`, `init-all` |
| Directory scanning | Done             | Multi-path discovery with auto-inference          |
| Daemon integration | Done             | `AppRegistry` in the daemon, `apps.*` RPC methods  |
| Process lifecycle  | Done             | Supervisor services `app-<name>`: restart, logs, status |
| Sandbox mode       | Flag only        | `sandbox: true` in manifest, not wired to `sandbox.py` |
| HTTP routes        | Done             | `/api/v1/apps`, see [HTTP API](#http-api)         |
| Agent integration  | Not started      | Agents can't discover or interact with apps yet   |
| App generation     | Specs only       | Prompt specs in `data/appbuilder/`, no pipeline   |

## Future work

- **Autostart** — a manifest flag to start apps when the daemon starts
- **Sandbox integration** — when `sandbox: true`, use `PythonSandbox` /
  `NodeJsSandbox` from `sandbox.py` instead of bare subprocess
- **UI** — add the `/apps` routes to the UI router, show status and
  start/stop buttons, and serve running apps from their port
- **Agent integration** — let agents discover, start, and generate apps
- **App generation pipeline** — execute `data/appbuilder/` specs via LLM,
  parse output, write files, create manifest
- **Persistent logs** — app output is kept in the supervisor's in-memory
  ring buffer only (last 400 lines); it is lost when the daemon stops
