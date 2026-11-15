# geenii server

Start, stop and inspect the geenii HTTP server: the FastAPI API (`/api/v1`)
plus the web UI it serves (see [server](../developer-guide/server.md)).

## Synopsis

```
geenii server <command>
```

## State file

A running server is recorded in `$GEENII_CACHE_DIR/server.json` (PID, process
start time, host and port or Unix socket, log file). `start` writes it in both foreground and
detached mode, so `stop` and `status` work from any terminal. A file left by a
crashed server is ignored and removed.

## Commands

### start

```
geenii server start [--host HOST] [--port PORT | --uds [PATH]] [--detach] [--reload] [--log-file PATH] [--wait SECONDS]
```

Run the server. Fails if a geenii server is already running.

| Option | Short | Default | Description |
|---|---|---|---|
| `--host` | | `GEENII_SERVER_HOST`, else `127.0.0.1` | Bind address |
| `--port` | `-p` | `GEENII_SERVER_PORT`, else `33311` | Port |
| `--uds` | | `GEENII_SERVER_SOCKET` | Listen on a Unix socket instead of host/port; without a path, `$GEENII_CACHE_DIR/server.sock` |
| `--detach` | `-d` | | Run in the background; returns once `/api/v1/health` answers |
| `--reload` | | | Restart on source changes (development) |
| `--log-file` | | `$GEENII_CACHE_DIR/logs/server.log` | Output of a detached server (appended) |
| `--wait` | | `60` | With `--detach`: seconds to wait for the server to become healthy |

Without `--detach` the server runs in the foreground until Ctrl-C or
`geenii server stop`. With `--detach`, the command exits with code 1 if the
server dies during startup (printing the end of its log) or isn't healthy in
time.

### Unix socket

With `--uds`, the server listens on a Unix domain socket instead of TCP.
`--uds` can't be combined with an explicit `--host` or `--port`.

- The socket is created with mode `0600`, so only the owner can connect.
- A leftover socket file from a server that didn't shut down cleanly is
  replaced. If something is still serving on it, or the path is a regular
  file, `start` fails.
- The socket file is removed when the server stops.
- Socket paths are limited to about 104 bytes on macOS (108 on Linux).

A browser can't open a Unix socket. To use the web UI, put a reverse proxy
(e.g. nginx `proxy_pass http://unix:/path/server.sock;`) in front of it.
Clients such as curl can talk to it directly:

```bash
curl --unix-socket ~/.cache/geenii/server.sock http://localhost/api/v1/health
```

### stop

```
geenii server stop [--timeout SECONDS]
```

Send SIGTERM, wait up to `--timeout` (default 10s), then SIGKILL. With
`--reload`, the reloader's worker process is stopped too. Exits with code 1 if
no server is running.

### status

```
geenii server status [--json]
```

Print PID, URL (`unix:PATH` for a socket), uptime, log file, and whether `/api/v1/health` answers. Exits
with code 1 if no server is running.

## Examples

```bash
geenii server start                 # foreground on 127.0.0.1:33311
geenii server start -d -p 8080      # background on port 8080
geenii server start -d --uds        # background on $GEENII_CACHE_DIR/server.sock
geenii server status
geenii server stop
```
