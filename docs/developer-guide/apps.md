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
  "manifest_version": "1",
  "type": "statichtml",
  "title": "My App",
  "description": "A small demo app",
  "author": "phil",
  "version": "1.0.0",
  "main": "index.html",
  "port": 9100,
  "env": {},
  "sandbox": false,
  "autostart": false
}
```

`name` and `title` are required. All other fields have sensible defaults. Both
versions are strings; a number (e.g. `1`) is read as one, `null` is invalid.

| Field         | Default     | Description                                          |
|---------------|-------------|------------------------------------------------------|
| `name`        | *(required)* | Unique app identifier                               |
| `manifest_version` | `"1"`  | Version of the manifest format                       |
| `type`        | `statichtml` | One of `statichtml`, `python`, `node`, `binary`     |
| `title`       | *(required)* | Human-readable display name                         |
| `description` | `null`      | Short description                                    |
| `author`      | `null`      | Author name                                          |
| `version`     | `"0.0.0"`   | The app's version (semver), always set            |
| `main`        | `null`      | Entry point file (auto-detected per type if omitted) |
| `port`        | `null`      | Preferred port (auto-allocated if omitted)           |
| `env`         | `{}`        | Environment variables passed to the process          |
| `sandbox`     | `false`     | Run inside Docker sandbox (not yet wired)            |
| `autostart`   | `false`     | Default for starting the app when the daemon starts or discovers it, once the app is enabled; the user's [app settings](#app-settings) override it |

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

The title of an inferred manifest comes from the directory name
(`title_from_name`: `my-cool_app` → `My Cool App`).

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
- `read_app_settings()` / `save_app_settings(app_path, **fields)` — the
  user's app settings (see [App settings](#app-settings))

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

An app removed from disk while running keeps running; stop it with
`geenii supervisor stop app-<name>`.

### App settings

The user's per-app settings live in the user settings file
(`~/.geenii/settings.json`, `config.user_settings_path()`), under `apps`,
keyed by the app's resolved directory (app names can repeat across
projects). Nothing is written into app directories.

```json
{
  "apps": {
    "/home/me/.geenii/apps/my-app": {"enabled": true, "autostart": true}
  }
}
```

| Key | Default | Meaning |
|---|---|---|
| `enabled` | `false` | Apps are disabled until the user enables (installs) them. A disabled app can't be started (`apps.start`/`apps.restart` fail) and isn't autostarted, even with `autostart` in its manifest. Disabling a started app stops it |
| `autostart` | the manifest's `autostart` | See [Autostart](#autostart) |
| `added` | `false` | The app was [added by its path](#adding-an-app-by-path); the registry loads it from this entry |

`AppSettings` validates an entry; unknown keys are kept. `AppRegistry.reload()`
reads the settings, so the daemon reads them at start and on every rescan;
there is no file watcher. `apps.set_enabled` and `apps.set_autostart`
(`PUT /apps/{name}/enabled`, `PUT /apps/{name}/autostart`, `geenii apps
enable|disable|autostart`, and the switches in the UI console's
`#/console/configure/apps`) write the file with `save_app_settings()` and
update the daemon's copy of the app. Disabling a started app also stops it;
otherwise they don't start or stop the app: autostart applies at the next
daemon start.

### Adding an app by path

An app directory outside the app directories can be added by its absolute
path: `apps.add` (`POST /apps/add`, the **Add App** dialog in the UI
console). The directory must exist and have a valid `manifest.json`; the
app is named after the manifest's `name` (scanned apps are named after
their directory). `AppRegistry.add_app()` refuses a directory that is
already known or a name that is taken, then saves
`{"added": true, "enabled": false}` in the app settings, so the app starts
out disabled, under Available.

`AppRegistry.reload()` loads every `added` entry the directory scan didn't
find. Entries whose directory or manifest is gone, or whose name is taken
by a scanned app, are logged and skipped.

`save_app_settings()` goes through `config.update_user_settings()`, which
keeps the file's other keys, refuses to overwrite a malformed file, and
writes atomically.

### Autostart

Apps that are enabled and have autostart (the user's app settings, else the
manifest's `autostart`) are started by the daemon:

- when it starts, for the apps it knows then (`~/.geenii/apps`)
- when a rescan discovers them: a new app directory sent as `dirs` (e.g. a
  project's `.geenii/apps`, the first time a client sends it) or a new app
  found by `apps.reload`

Apps are disabled by default, so a newly found app is only autostarted if
it was already enabled in the user settings. Enabling an app doesn't start
it; its autostart applies from the next daemon start.

An autostart app that is already started, or that was stopped and is still
on disk, is not started again by a rescan; it starts again with the next
daemon start. An app that fails to start is logged and skipped.

Each autostart is recorded in the process event log (`app.autostart`, actor
`daemon`).

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
| `POST /apps/{name}/start` | Optional body `{"port": int}`. App info. 409 already started or disabled |
| `POST /apps/{name}/stop` | App info. 409 not started |
| `POST /apps/{name}/restart` | Optional body `{"port": int}`; keeps the port if omitted. App info |
| `GET /apps/{name}/logs?tail=200` | `{"name", "lines"}`; `lines` is empty if the app never ran |
| `POST /apps/reload` | `{"added", "removed", "autostarted", "dirs"}` |
| `PUT /apps/{name}/autostart` | Body `{"autostart": bool}`. Saves the app's autostart in the user settings; applies at the next daemon start. App info |
| `POST /apps/add` | Body `{"path": str}`, an absolute app directory with a `manifest.json`. Adds it disabled. App info. 400 missing directory or manifest, invalid manifest or relative path; 409 already added or name taken |
| `PUT /apps/{name}/enabled` | Body `{"enabled": bool}`. Enables or disables the app in the user settings; disabling a running app stops it. App info |

Every route except the two reads returns 409 when the daemon isn't running,
and 503 when it can't be reached. Unknown apps are 404, and invalid params
are 400 or 422.

## UI

`geenii-ui/src/app/apps/` uses the HTTP API:

- `apps-api.ts` — types, the `useApps(poll = true)` / `useApp(name)` hooks
  (polled every 5 s while the daemon runs; `useApps(false)` loads once),
  `useAppAction()`, `useSetAppSetting()`, and `useAppUrl()`: a running app is
  reached at `http://<API server host>:<port>/`
- `apps-components.tsx` — status badge, start/stop/restart controls, log
  viewer (polled every 2 s while open)
- `#/` launcher, **Apps** tab (`launcher/launcher-apps.tsx`) — icon tiles
  of the enabled apps with a status dot, filtered by the launcher search.
  Clicking a tile opens `#/apps/<name>`, starting the app first if it is
  stopped; a hover button starts or stops it in place. The list is polled only
  while the tab is shown. A **Manage your apps** link leads to the console
  app settings
- `#/apps` (`apps-page.tsx`, `apps-view.tsx`) — app cards with status and
  controls (not linked in the navigation)
- `#/apps/<name>` (`app-page.tsx`) — the running app in an iframe, plus its
  log and details
- `#/console/configure/apps` (`console/components/apps-settings.tsx`) — tabs
  **Installed** (enabled apps) and **Available** (disabled apps, with an
  **Install** button = enable). Each card shows the status dot and badge,
  the title (click opens `#/apps/<name>`) and the description; its settings
  button opens a dialog with the app's info (name, type, version, path,
  service, port, process, last exit), Start/Stop/Restart, the Autostart
  switch and **Install**/**Uninstall** (uninstall = disable and stop; files
  are never added or removed). A third tab, **Marketplace**
  (`apps/marketplace-view.tsx`: app bundles from a catalog, a dummy view with
  sample data in `apps/marketplace-catalog.json`; its Install button only
  says installing isn't available yet; shown only with
  `VITE_FEATURE_APPS_MARKETPLACE=true`); **Refresh**, **Rescan**
  (`POST /apps/reload`) and **Add App**, a dialog with a form to add an app
  directory by its path (`POST /apps/add`; the new app shows under
  Available) and a note on copying apps into the app directories

The desktop app's CSP allows frames from `http://localhost:*` and
`http://127.0.0.1:*` for this. `tauri-app-viewer.tsx` (static files through
the `geenii://` scheme) is no longer used by the app page.

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
| UI                 | Done             | Launcher Apps tab, `#/apps/<name>`, console app settings, see [UI](#ui) |
| Autostart          | Done             | Manifest `autostart`, see [Autostart](#autostart) |
| Agent integration  | Not started      | Agents can't discover or interact with apps yet   |
| App generation     | Specs only       | Prompt specs in `data/appbuilder/`, no pipeline   |

## Future work

- **Sandbox integration** — when `sandbox: true`, use `PythonSandbox` /
  `NodeJsSandbox` from `sandbox.py` instead of bare subprocess
- **Agent integration** — let agents discover, start, and generate apps
- **App generation pipeline** — execute `data/appbuilder/` specs via LLM,
  parse output, write files, create manifest
- **Persistent logs** — app output is kept in the supervisor's in-memory
  ring buffer only (last 400 lines); it is lost when the daemon stops
