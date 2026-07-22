# Apps (GeeApps)

A GeeApp is a sandboxed micro-application managed by geenii. Three app types
are supported:

| Type     | Runtime               | Default entry point | Launch command                  |
|----------|-----------------------|---------------------|---------------------------------|
| `webapp` | Python `http.server`  | `index.html`        | `python3 -m http.server $PORT`  |
| `node`   | Node.js               | `index.js`          | `npm start` or `node $main`     |
| `binary` | None (compiled)       | *(must be set)*     | `./$main`                       |

## Concepts

A GeeApp is a thin wrapper around a directory of files plus a manifest that
tells geenii how to run them. The registry discovers apps, reads (or infers)
their manifests, and manages their lifecycle — start, stop, status, logs.

Port allocation is automatic (starting at 9100) but can be overridden per
app via the manifest `port` field or the `--port` CLI flag.

## App directory layout

```
apps/
└── my-app/
    ├── manifest.json       # metadata + launch config
    ├── index.html          # entry point (webapp)
    ├── script.js           # optional
    └── styles.css          # optional
```

## App discovery paths

Apps are discovered from multiple directories (checked in order):

1. `~/.geenii/apps` — user-global apps
2. `$GEENII_WORKING_DIR/.geenii/apps` — workspace-local apps
3. `$GEENII_DIR/apps` — project apps

The CLI also accepts `--dir` to add extra directories at runtime.

## Manifest (`manifest.json`)

```json
{
  "name": "my-app",
  "type": "webapp",
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
| `type`        | `webapp`    | One of `webapp`, `node`, `binary`                    |
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
2. `index.html` present → `webapp`
3. Executable binary named after the directory → `binary`
4. Fallback → `webapp`

Use `geenii apps init <name>` or `geenii apps init-all` to write inferred
manifests to disk.

## Source code

### `src/geenii/apps.py`

**Enums:**

- `AppType` — `webapp`, `node`, `binary`
- `AppStatus` — `stopped`, `starting`, `running`, `error`

**Models:**

- `GeeAppManifest` — Pydantic model for `manifest.json`
- `GeeApp` — wraps a manifest with filesystem path, trusted flag, and
  process lifecycle (`start()`, `stop()`, `status`, `pid`, `port`, `logs()`,
  `info()`)

**Registry:**

`AppRegistry` — discovery, registration, and lifecycle management:

- `load_from_directory(path, trusted=False)` — scan a directory, read or
  infer manifests, register all apps
- `start_app(name, port=None)` — launch with auto-allocated or explicit port
- `stop_app(name)` — send SIGTERM, then SIGKILL after 10s timeout
- `stop_all()` — stop every running app
- `get(name)` / `list()` / `names()` — lookups
- `register(app)` / `unregister(name)` — manual registration

**Helpers:**

- `read_manifest(app_dir)` — read and validate `manifest.json`, returns
  `None` if missing
- `infer_manifest(app_dir, name)` — auto-detect type from directory contents
- `write_manifest(app_dir, manifest)` — write `manifest.json` to disk

### `src/geenii/cli/apps_cli.py`

Click command group registered as `geenii apps`. See
[CLI reference](../cli-reference/apps.md) for full usage.

## Launch behaviour by type

### `webapp`

Serves the app directory with Python's built-in `http.server`. The entry
point (`main`) defaults to `index.html`. The server runs on the assigned
port with `cwd` set to the app directory, so all relative paths resolve
correctly.

### `node`

If `package.json` exists, runs `npm start`. Otherwise runs `node <main>`
where `main` defaults to `index.js` (or `server.js` if present). The `PORT`
environment variable is set if a port is assigned.

### `binary`

Executes the binary at `<app_dir>/<main>` directly. The `main` field is
required — inference looks for an executable file named after the app
directory. No runtime needed.

## Current status

| Area               | Status           | Notes                                             |
|--------------------|------------------|---------------------------------------------------|
| Models & registry  | Done             | `GeeAppManifest`, `GeeApp`, `AppRegistry`         |
| CLI commands        | Done             | `list`, `info`, `start`, `stop`, `init`, `init-all` |
| Directory scanning | Done             | Multi-path discovery with auto-inference          |
| Process lifecycle  | Done             | Start/stop/status/pid/port tracking               |
| Sandbox mode       | Flag only        | `sandbox: true` in manifest, not wired to `sandbox.py` |
| HTTP routes        | Not active       | Old router in `bak/route_apps.py`, needs rewrite  |
| Agent integration  | Not started      | Agents can't discover or interact with apps yet   |
| App generation     | Specs only       | Prompt specs in `data/appbuilder/`, no pipeline   |

## Future work

- **Sandbox integration** — when `sandbox: true`, use `PythonSandbox` /
  `NodeJsSandbox` from `sandbox.py` instead of bare subprocess
- **HTTP routes** — restore and fix the FastAPI router for serving app files
  and listing apps via API
- **Agent integration** — let agents discover, start, and generate apps
- **App generation pipeline** — execute `data/appbuilder/` specs via LLM,
  parse output, write files, create manifest
- **Log capture** — route subprocess stdout/stderr to log files for
  `geenii apps logs <name>`
