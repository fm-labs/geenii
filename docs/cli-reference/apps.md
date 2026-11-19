# geenii apps

List, inspect, start, stop, and initialize GeeApps (micro applications).

## Synopsis

```
geenii apps [--socket PATH] <command> [OPTIONS]
```

## The daemon

Apps run inside the [geenii daemon](daemon.md) as supervisor services named
`app-<name>`, so they keep running after the CLI exits and stop when the
daemon stops. Apps are disabled until you enable them (see `enable` below);
enabled apps with autostart (see `autostart` below) start with the daemon.
Start the daemon first:

```bash
geenii daemon start
```

Without a running daemon, every command except `init` and `init-all` exits
with code 1.

| Option | Short | Description |
|---|---|---|
| `--socket` | `-s` | Path to the daemon's Unix socket (env: `GEENII_SOCKET`, `GEENII_PM_SOCKET`) |

## App Discovery

The daemon always knows the user apps in `~/.geenii/apps`. Each command also
sends these directories to the daemon, which adds them to its app registry
and keeps them until it stops:

1. `~/.geenii/apps` — user-global apps
2. `.geenii/apps` — project apps (relative to `GEENII_WORKING_DIR`), if it exists
3. `--dir` — an extra directory, if given

When two directories contain an app with the same name, the later one wins.

## Commands

### list

```
geenii apps list [--json] [--dir DIR]
```

List all apps with type, status (`running`, `starting`, `error`, `stopped`),
port and pid.

| Option | Description |
|---|---|
| `--json` | Print the raw app list as JSON |
| `--dir` | Additional apps directory |

### info

```
geenii apps info <NAME> [--json] [--dir DIR]
```

Show details for an app: type, title, status, port, pid, path, service name,
trust and sandbox flags, failures and last exit.

### start

```
geenii apps start <NAME> [--port PORT] [--dir DIR]
```

Start an app as a background service of the daemon. Static HTML apps launch
`python3 -m http.server`, python apps run `<python> <main>` (using the app's
`.venv` if present), node apps run `npm start` or `node <main>`, binaries
execute directly. The supervisor restarts the app when it exits.

The port is the `--port` value, else the port the app had before, else the
manifest `port`, else a random free port from 42000-44000. It stays with the app
across restarts. Fails if the app is already started.

| Option | Short | Description |
|---|---|---|
| `--port` | `-p` | Port to serve on (auto-allocated if omitted) |
| `--dir` | | Additional apps directory |

### stop

```
geenii apps stop <NAME> [--dir DIR]
```

Stop a running app (SIGTERM, then SIGKILL after the grace period) and remove
its service from the supervisor.

### restart

```
geenii apps restart <NAME> [--port PORT] [--dir DIR]
```

Restart an app with its current manifest, so manifest changes take effect.
Starts the app if it is stopped. Without `--port`, the app keeps its port.

### logs

```
geenii apps logs <NAME> [--tail N] [--dir DIR]
```

Show the app's recent output, as kept by the supervisor (lines prefixed with
`[stdout]`, `[stderr]` or `[supervisor]`).

| Option | Short | Description |
|---|---|---|
| `--tail` | `-n` | Number of lines to show (default 100) |

### reload

```
geenii apps reload [--dir DIR]
```

Rescan all app directories, picking up new, removed and changed apps, and
start new enabled apps that have `autostart` set. Running apps keep running; use
`restart` to apply manifest changes to them.

### enable / disable

```
geenii apps enable <NAME> [--dir DIR]
geenii apps disable <NAME> [--dir DIR]
```

Enable or disable an app. Apps are disabled by default: enable an app before
starting it. Disabling a running app stops it; a disabled app can't be
started and isn't autostarted. Saved in the user
settings (`~/.geenii/settings.json`, `apps`), not in the app directory.

### autostart

```
geenii apps autostart <NAME> on|off [--dir DIR]
```

Turn starting the app with the daemon on or off. Saved in the user settings
and applied at the next daemon start; it overrides the manifest's
`autostart`. Only enabled apps are autostarted.

### init

```
geenii apps init <NAME> [OPTIONS]
```

Generate a `manifest.json` for an existing app directory. The app type is
auto-detected from directory contents unless `--type` is given. Refuses to
overwrite an existing manifest. Works without the daemon; if it runs, it
reloads its apps afterwards.

| Option | Short | Description |
|---|---|---|
| `--type` | `-t` | App type: `statichtml`, `python`, `node`, or `binary` (auto-detected if omitted) |
| `--title` | | Human-readable title |
| `--description` | | Short description |
| `--autostart` | | Write `"autostart": true` as the manifest default |
| `--dir` | | Additional apps directory to search |

### init-all

```
geenii apps init-all [OPTIONS]
```

Batch-generate `manifest.json` for all app directories that lack one.
Prints each app with its inferred type. Works without the daemon.

| Option | Description |
|---|---|
| `--overwrite` | Overwrite existing manifests |
| `--dir` | Apps directory to scan (defaults to all known paths) |

## Examples

```bash
# List apps, including those in a custom directory
geenii apps list --dir ./my-apps

# Inspect an app
geenii apps info hello-world

# Start an app on a specific port, then follow its output
geenii apps start hello-world --port 8080
geenii apps logs hello-world

# Apply manifest changes to a running app
geenii apps restart hello-world

# Stop a running app
geenii apps stop hello-world

# Generate a manifest for a single app
geenii apps init my-app --type node --title "My Node App"

# Generate manifests for all apps
geenii apps init-all --dir ./my-apps
```
