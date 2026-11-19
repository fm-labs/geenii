import logging
import os
import random
import re
import socket
from enum import Enum
import webbrowser

import pydantic

from geenii import config
from geenii.supervisor import ServiceConfig
from geenii.utils.os_util import detect_os

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "manifest.json"
APP_SERVICE_PREFIX = "app-"  # supervisor service name prefix, avoids clashes with other services
DEFAULT_STATIC_PORT = 8000
APP_PORT_RANGE = (42000, 44000)  # apps without a fixed port get a random free port from this range (inclusive)
PYTHON_MAIN_CANDIDATES = ("main.py", "app.py", "server.py")
PYTHON_PROJECT_MARKERS = ("pyproject.toml", "requirements.txt", *PYTHON_MAIN_CANDIDATES)
CONTAINER_IMAGE_PREFIX = "geenii-app-"
# Docker repository name component: lowercase alnum, single separators, no leading/trailing ones
CONTAINER_IMAGE_RE = re.compile(r"[a-z0-9]+(?:(?:[._]|__|-+)[a-z0-9]+)*")
ENV_NAME_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _find_python_main(app_dir: str) -> str | None:
    for candidate in PYTHON_MAIN_CANDIDATES:
        if os.path.isfile(os.path.join(app_dir, candidate)):
            return candidate
    return None


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _python_executable(app_dir: str) -> str:
    """The app's own virtualenv interpreter if it has one, else python3 from PATH"""
    for venv in (".venv", "venv"):
        for rel in (("bin", "python"), ("Scripts", "python.exe")):
            candidate = os.path.join(app_dir, venv, *rel)
            if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate
    return "python3"


class AppType(str, Enum):
    STATICHTML = "statichtml"
    PYTHON = "python"
    NODE = "node"
    BINARY = "binary"
    CONTAINER = "container"
    LINK = "link"


class AppStatus(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


class GeeAppManifest(pydantic.BaseModel):
    model_config = {"extra": "allow"}

    name: str
    manifest_version: str = "1"
    version: str = "0.0.0"
    title: str
    type: AppType = AppType.STATICHTML
    description: str | None = None
    author: str | None = None
    main: str | None = None
    port: int | None = None
    env: dict[str, str] = pydantic.Field(default_factory=dict)
    sandbox: bool = False
    # Default for starting the app when the daemon starts or discovers it; the user's
    # app settings (AppSettings.autostart) override it
    autostart: bool = False

    @pydantic.field_validator("manifest_version", "version", mode="before")
    @classmethod
    def _version_str(cls, value):
        """Versions are strings; a number (e.g. `1`) is read as one"""
        if isinstance(value, bool):
            raise ValueError("must be a string or a number")
        if isinstance(value, (int, float)):
            return str(value)
        return value


class AppSettings(pydantic.BaseModel):
    """The user's settings for one app, stored in the user settings file (`apps`, keyed by app directory)"""

    model_config = {"extra": "allow"}

    # A disabled app can't be started and isn't autostarted
    enabled: bool = False
    # None: the manifest's `autostart`
    autostart: bool | None = None
    # Added by its path (AppRegistry.add_app) rather than found in an app directory:
    # the registry loads it from this settings entry
    added: bool = False


def app_settings_key(app_path: str) -> str:
    """Key of an app in the `apps` settings: its resolved directory (names can repeat across projects)"""
    return os.path.realpath(app_path)


def read_app_settings() -> dict[str, AppSettings]:
    """The `apps` section of the user settings; invalid entries are logged and skipped"""
    raw = config.read_user_settings().get("apps") or {}
    if not isinstance(raw, dict):
        logger.error("Ignoring the 'apps' user settings: expected an object keyed by app directory")
        return {}
    result = {}
    for path, entry in raw.items():
        try:
            result[app_settings_key(path)] = AppSettings.model_validate(entry or {})
        except pydantic.ValidationError as e:
            logger.error(f"Ignoring invalid app settings for {path}: {e}")
    return result


def save_app_settings(app_path: str, **fields) -> AppSettings:
    """Set FIELDS of an app's entry in the user settings file; returns the entry"""
    key = app_settings_key(app_path)
    result: dict = {}

    def update(settings: dict) -> None:
        apps = settings.get("apps")
        if not isinstance(apps, dict):
            apps = settings["apps"] = {}
        entry = apps.get(key) if isinstance(apps.get(key), dict) else {}
        entry.update(fields)
        # Validate before writing, so a bad value never reaches the file
        result["settings"] = AppSettings.model_validate(entry)
        apps[key] = entry

    config.update_user_settings(update)
    return result["settings"]


class GeeApp(pydantic.BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    name: str
    path: str
    manifest: GeeAppManifest
    trusted: bool = False
    settings: AppSettings = pydantic.Field(default_factory=AppSettings)

    _assigned_port: int | None = pydantic.PrivateAttr(default=None)

    @property
    def enabled(self) -> bool:
        return self.settings.enabled

    @property
    def autostart(self) -> bool:
        """The user's setting, else the manifest default"""
        if self.settings.autostart is not None:
            return self.settings.autostart
        return self.manifest.autostart

    @property
    def port(self) -> int | None:
        return self._assigned_port or self.manifest.port

    def info(self) -> dict:
        """Static app info (runtime state comes from the supervisor service)"""
        return {
            "name": self.name,
            "type": self.manifest.type.value,
            "title": self.manifest.title,
            "description": self.manifest.description,
            "version": self.manifest.version,
            "port": self.port,
            "path": self.path,
            "trusted": self.trusted,
            "sandbox": self.manifest.sandbox,
            "enabled": self.enabled,
            "autostart": self.autostart,
            "added": self.settings.added,
            "service": self.service_name,
        }

    @property
    def service_name(self) -> str:
        """Name of the app's background service in the supervisor"""
        return f"{APP_SERVICE_PREFIX}{self.name}"

    def to_service_config(self, port: int | None = None, restart: bool = True) -> ServiceConfig:
        """Supervisor service config that runs this app as a background service.

        Only the app's own env vars (manifest env + PORT) are included; the supervisor
        merges them into its own environment at spawn time.
        """
        cmd, env = self._build_launch_command(self._resolve_port(port))
        return ServiceConfig(
            name=self.service_name,
            cmd=cmd,
            env=env,
            cwd=self.path,
            restart=restart if self.manifest.type is not AppType.LINK else False,
        )

    def _resolve_port(self, port: int | None = None) -> int | None:
        """Explicit port > port assigned at the last start > manifest port"""
        return port or self._assigned_port or self.manifest.port

    def _build_launch_command(self, port: int | None) -> tuple[list[str], dict[str, str]]:
        """Command and app-specific env vars (not including os.environ) to launch the app"""
        env = dict(self.manifest.env)
        main = self.manifest.main
        app_type = self.manifest.type

        if app_type == AppType.STATICHTML:
            port = port or DEFAULT_STATIC_PORT
            env["PORT"] = str(port)
            return ["python3", "-m", "http.server", str(port)], env

        if port is not None:
            env["PORT"] = str(port)

        if app_type == AppType.PYTHON:
            main = main or _find_python_main(self.path) or "main.py"
            # Unbuffered so output reaches the logs line by line
            env.setdefault("PYTHONUNBUFFERED", "1")
            return [_python_executable(self.path), main], env

        if app_type == AppType.NODE:
            main = main or "index.js"
            if os.path.isfile(os.path.join(self.path, "package.json")):
                return ["npm", "start"], env
            return ["node", main], env

        if app_type == AppType.BINARY:
            if main is None:
                raise ValueError(f"App '{self.name}' is type 'binary' but has no 'main' set in manifest")
            bin_path = os.path.join(self.path, main)
            if not os.path.isfile(bin_path):
                raise FileNotFoundError(f"Binary not found: {bin_path}")
            return [bin_path], env

        if app_type == AppType.CONTAINER:
            return self._container_launch_command(port, env), env

        if app_type == AppType.LINK:
            if main is None or not main.startswith("http"):
                raise ValueError(f"App '{self.name}' is type 'url' but has no url set in 'main'")
            # os_type = detect_os()
            # if os_type == "windows":
            #     cmd = ["cmd.exe", "/C", "start", "", main]
            #     #cmd = ["ps", "Start-Process", main] # powershell
            # elif os_type == "linux":
            #     cmd = ["xdg-open", main]
            # elif os_type == "darwin":
            #     cmd = ["open", main]
            # else:
            return ["python", "-m", "webbrowser", main], env

        raise ValueError(f"Unknown app type: {app_type}")

    def _container_launch_command(self, port: int | None, env: dict[str, str]) -> list[str]:
        """`docker build` then `docker run` as one supervised process.

        The supervisor spawns an argv list without a shell, so `&&` needs `sh -c`. The script is
        a constant; every variable value is passed as a positional arg ($1..$n), so nothing from
        the manifest or the app path is ever parsed by the shell.
        """
        if port is None or not (1 <= port <= 65535):
            raise ValueError(f"App '{self.name}' is type 'container' but has no valid port: {port!r}")

        image = f"{CONTAINER_IMAGE_PREFIX}{self.name.lower()}"
        if not CONTAINER_IMAGE_RE.fullmatch(image):
            raise ValueError(f"App name '{self.name}' is not usable as a docker image name")

        app_dir = os.path.realpath(self.path)
        dockerfile = os.path.realpath(os.path.join(app_dir, self.manifest.main or "Dockerfile"))
        if os.path.commonpath([app_dir, dockerfile]) != app_dir:
            raise ValueError(f"Dockerfile must be inside the app directory: {self.manifest.main}")
        if not os.path.isfile(dockerfile):
            raise FileNotFoundError(f"Dockerfile not found: {dockerfile}")
        # The supervisor runs os.path.expandvars on every arg
        if "$" in app_dir:
            raise ValueError(f"App path must not contain '$': {app_dir}")

        # `-e NAME` without a value: docker reads it from its own env (the supervisor merges
        # ENV into it), so values never show up in the argv / process list
        env_flags: list[str] = []
        for key in env:
            if not ENV_NAME_RE.fullmatch(key):
                raise ValueError(f"Invalid env var name in manifest: {key!r}")
            env_flags += ["-e", key]

        script = 'docker build -f "$1" -t "$2" "$3" && shift 3 && exec docker run "$@"'
        return [
            "sh", "-c", script, "sh",  # "sh" is $0
            dockerfile, image, app_dir,
            "--rm", "--name", self.service_name,
            "-p", f"127.0.0.1:{port}:80",
            *env_flags,
            image,
        ]


def read_manifest(app_dir: str) -> GeeAppManifest | None:
    manifest_path = os.path.join(app_dir, MANIFEST_FILENAME)
    if not os.path.isfile(manifest_path):
        return None
    with open(manifest_path, "r") as f:
        data = f.read()
    return GeeAppManifest.model_validate_json(data)


def title_from_name(name: str) -> str:
    """A display title for an app name: `my-app_v2` -> `My App V2`"""
    words = re.split(r"[\s_\-.]+", name.strip())
    return " ".join(w[:1].upper() + w[1:] for w in words if w) or name


def infer_manifest(app_dir: str, name: str) -> GeeAppManifest:
    """A manifest for an app directory without one: the type from its files, the title from NAME"""
    title = title_from_name(name)
    if os.path.isfile(os.path.join(app_dir, "package.json")):
        main = "index.js"
        if os.path.isfile(os.path.join(app_dir, "server.js")):
            main = "server.js"
        return GeeAppManifest(name=name, title=title, type=AppType.NODE, main=main)

    if any(os.path.isfile(os.path.join(app_dir, m)) for m in PYTHON_PROJECT_MARKERS):
        return GeeAppManifest(name=name, title=title, type=AppType.PYTHON, main=_find_python_main(app_dir))

    if os.path.isfile(os.path.join(app_dir, "index.html")):
        return GeeAppManifest(name=name, title=title, type=AppType.STATICHTML, main="index.html")

    for ext in ("", ".exe"):
        candidate = os.path.join(app_dir, name + ext)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return GeeAppManifest(name=name, title=title, type=AppType.BINARY, main=name + ext)

    return GeeAppManifest(name=name, title=title, type=AppType.STATICHTML)


def load_app(app_dir: str, trusted: bool = False) -> GeeApp:
    """The app in APP_DIR, which must have a valid manifest; named after the manifest's `name`.

    Raises ValueError if the directory doesn't exist or has no (valid) manifest.
    """
    if not os.path.isdir(app_dir):
        raise ValueError(f"Directory not found: {app_dir}")
    try:
        manifest = read_manifest(app_dir)
    except (OSError, ValueError) as e:
        raise ValueError(f"Invalid {MANIFEST_FILENAME} in {app_dir}: {e}") from e
    if manifest is None:
        raise ValueError(f"No {MANIFEST_FILENAME} in {app_dir}")
    return GeeApp(name=manifest.name, path=app_dir, manifest=manifest, trusted=trusted)


def write_manifest(app_dir: str, manifest: GeeAppManifest) -> str:
    manifest_path = os.path.join(app_dir, MANIFEST_FILENAME)
    with open(manifest_path, "w") as f:
        f.write(manifest.model_dump_json(indent=2, exclude_none=True))
    return manifest_path


class AppRegistry:
    """Apps discovered in a list of directories; later directories override earlier ones on name clashes"""

    def __init__(self, dirs: list[str] | None = None):
        self._apps: dict[str, GeeApp] = {}
        self._dirs: list[str] = []
        for d in dirs or []:
            self.add_dir(d)

    @property
    def dirs(self) -> list[str]:
        return list(self._dirs)

    def add_dir(self, directory: str) -> bool:
        """Add a directory to scan (absolute path); True if it was new. Call reload() to scan it."""
        directory = os.path.abspath(os.path.expanduser(directory))
        if directory in self._dirs:
            return False
        self._dirs.append(directory)
        return True

    def reload(self) -> dict[str, list[str]]:
        """Rescan all directories and re-read the app settings. Ports of apps that still exist are kept."""
        # Scan into a fresh registry and swap at the end, so readers never see a half-loaded one
        fresh = AppRegistry()
        for d in self._dirs:
            if os.path.isdir(d):
                fresh.load_from_directory(d)
        settings = read_app_settings()
        fresh._load_added_apps(settings)
        old = self._apps
        for name, app in fresh._apps.items():
            app.settings = settings.get(app_settings_key(app.path), AppSettings())
            if name in old:
                app._assigned_port = old[name]._assigned_port
        self._apps = fresh._apps
        return {
            "added": sorted(set(self._apps) - set(old)),
            "removed": sorted(set(old) - set(self._apps)),
        }

    def _load_added_apps(self, settings: dict[str, AppSettings]) -> None:
        """Load the apps added by path (`added` in their settings) that the directory scan didn't find"""
        known = {app_settings_key(a.path) for a in self._apps.values()}
        for path, entry in settings.items():
            if not entry.added or path in known:
                continue
            try:
                app = load_app(path)
            except ValueError as e:
                logger.warning(f"Skipping added app: {e}")
                continue
            if app.name in self._apps:
                logger.warning(
                    f"Skipping added app '{app.name}' in {path}: the name is taken by {self._apps[app.name].path}"
                )
                continue
            self.register(app)

    def add_app(self, app_dir: str) -> GeeApp:
        """Add the app in APP_DIR (a directory with a valid manifest) by its path, disabled.

        Saved in the user settings (`added`, `enabled: false`), so reload() keeps it.
        Raises ValueError for a missing directory or manifest, RuntimeError if the app is already
        known or its name is taken.
        """
        app_dir = os.path.abspath(os.path.expanduser(app_dir))
        app = load_app(app_dir)
        key = app_settings_key(app_dir)
        for other in self._apps.values():
            if app_settings_key(other.path) == key:
                raise RuntimeError(f"App '{other.name}' in {app_dir} is already added")
        if app.name in self._apps:
            raise RuntimeError(f"An app named '{app.name}' already exists in {self._apps[app.name].path}")
        app.settings = save_app_settings(app_dir, added=True, enabled=False)
        self.register(app)
        return app

    def register(self, app: GeeApp):
        self._apps[app.name] = app

    def get(self, name: str) -> GeeApp | None:
        return self._apps.get(name)

    def require(self, name: str) -> GeeApp:
        app = self.get(name)
        if app is None:
            raise KeyError(f"App '{name}' not found")
        return app

    def list(self) -> list[GeeApp]:
        return list(self._apps.values())

    def names(self) -> list[str]:
        return list(self._apps.keys())

    def unregister(self, name: str) -> bool:
        return self._apps.pop(name, None) is not None

    def assign_port(self, name: str, port: int | None = None) -> int:
        """Pin the app's port: the given one, else its current/manifest port, else a free one"""
        app = self.require(name)
        port = port or app.port or self._allocate_port()
        app._assigned_port = port
        return port

    def _allocate_port(self) -> int:
        """A random free port in APP_PORT_RANGE that no other app uses"""
        taken = {a.port for a in self._apps.values() if a.port}
        candidates = [p for p in range(APP_PORT_RANGE[0], APP_PORT_RANGE[1] + 1) if p not in taken]
        random.shuffle(candidates)
        for port in candidates:
            if _port_is_free(port):
                return port
        raise RuntimeError(f"No free port in range {APP_PORT_RANGE[0]}-{APP_PORT_RANGE[1]}")

    def load_from_directory(self, directory: str, trusted: bool = False):
        if not os.path.isdir(directory):
            logger.warning(f"App directory does not exist: {directory}")
            return

        count = 0
        for entry in sorted(os.listdir(directory)):
            entry_path = os.path.join(directory, entry)
            if not os.path.isdir(entry_path) or entry.startswith("."):
                continue

            try:
                manifest = read_manifest(entry_path)
            except (OSError, ValueError) as e:
                logger.error(f"Invalid manifest for app '{entry}' in {directory}: {e} — skipping")
                continue
            if manifest is None:
                manifest = infer_manifest(entry_path, entry)
                logger.debug(f"Inferred manifest for '{entry}': type={manifest.type.value}")

            app = GeeApp(name=entry, path=entry_path, manifest=manifest, trusted=trusted)
            self.register(app)
            count += 1
            logger.debug(f"Registered app '{entry}' ({manifest.type.value})")

        logger.info(f"Loaded {count} apps from {directory}")
