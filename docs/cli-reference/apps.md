# geenii apps

List, inspect, start, stop, and initialize GeeApps (micro applications).

## Synopsis

```
geenii apps <command> [OPTIONS]
```

## App Discovery

The CLI scans these directories for app subdirectories (first match wins for
a given name):

1. `~/.geenii/apps` — user-global apps
2. `.geenii/apps` — workspace-local apps (relative to `GEENII_WORKING_DIR`)
3. `$GEENII_DIR/apps` — project apps

All commands accept `--dir` to add an extra directory to the search path.

## Commands

### list

```
geenii apps list [OPTIONS]
```

List all discovered apps with type and optional runtime status.

#### Options

| Option | Short | Description |
|---|---|---|
| `--status` | `-s` | Show runtime status (`stopped`, `running`, `error`) |
| `--dir` | | Additional apps directory to scan |

### info

```
geenii apps info <NAME> [OPTIONS]
```

Show details for a specific app: type, status, port, pid, path, trust, and
sandbox flags.

#### Options

| Option | Short | Description |
|---|---|---|
| `--dir` | | Additional apps directory to scan |

### start

```
geenii apps start <NAME> [OPTIONS]
```

Start an app. Webapps launch `python3 -m http.server`, node apps run
`npm start` or `node <main>`, binaries execute directly. A port is
auto-allocated starting at 9100 unless `--port` is given.

#### Options

| Option | Short | Description |
|---|---|---|
| `--port` | `-p` | Port to serve on (auto-allocated if omitted) |
| `--dir` | | Additional apps directory to scan |

### stop

```
geenii apps stop <NAME> [OPTIONS]
```

Stop a running app. Sends `SIGTERM`, then `SIGKILL` after 10 seconds if
the process doesn't exit.

#### Options

| Option | Short | Description |
|---|---|---|
| `--dir` | | Additional apps directory to scan |

### init

```
geenii apps init <NAME> [OPTIONS]
```

Generate a `manifest.json` for an existing app directory. The app type is
auto-detected from directory contents unless `--type` is given. Refuses to
overwrite an existing manifest.

#### Options

| Option | Short | Description |
|---|---|---|
| `--type` | `-t` | App type: `webapp`, `node`, or `binary` (auto-detected if omitted) |
| `--title` | | Human-readable title |
| `--description` | | Short description |
| `--dir` | | Additional apps directory to scan |

### init-all

```
geenii apps init-all [OPTIONS]
```

Batch-generate `manifest.json` for all app directories that lack one.
Prints each app with its inferred type.

#### Options

| Option | Short | Description |
|---|---|---|
| `--overwrite` | | Overwrite existing manifests |
| `--dir` | | Apps directory to scan (defaults to all known paths) |

## Examples

```bash
# List apps from a custom directory
geenii apps list --dir ./data/apps

# Inspect an app
geenii apps info hello-world --dir ./data/apps

# Start an app on a specific port
geenii apps start hello-world --port 8080 --dir ./data/apps

# Stop a running app
geenii apps stop hello-world --dir ./data/apps

# Generate a manifest for a single app
geenii apps init my-app --type node --title "My Node App"

# Generate manifests for all apps
geenii apps init-all --dir ./data/apps
```
