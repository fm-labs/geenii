import os
import json
import signal
import logging
import subprocess
from enum import Enum
from typing import Literal

import pydantic

logger = logging.getLogger(__name__)

MANIFEST_FILENAME = "manifest.json"


class AppType(str, Enum):
    WEBAPP = "webapp"
    NODE = "node"
    BINARY = "binary"


class AppStatus(str, Enum):
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


class GeeAppManifest(pydantic.BaseModel):
    model_config = {"extra": "allow"}

    name: str
    type: AppType = AppType.WEBAPP
    title: str | None = None
    description: str | None = None
    author: str | None = None
    version: str | None = None
    main: str | None = None
    port: int | None = None
    env: dict[str, str] = pydantic.Field(default_factory=dict)
    sandbox: bool = False


class GeeApp(pydantic.BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    name: str
    path: str
    manifest: GeeAppManifest
    trusted: bool = False

    _process: subprocess.Popen | None = pydantic.PrivateAttr(default=None)
    _assigned_port: int | None = pydantic.PrivateAttr(default=None)

    @property
    def status(self) -> AppStatus:
        if self._process is None:
            return AppStatus.STOPPED
        rc = self._process.poll()
        if rc is None:
            return AppStatus.RUNNING
        if rc != 0:
            return AppStatus.ERROR
        return AppStatus.STOPPED

    @property
    def port(self) -> int | None:
        return self._assigned_port or self.manifest.port

    @property
    def pid(self) -> int | None:
        if self._process is not None and self._process.poll() is None:
            return self._process.pid
        return None

    def info(self) -> dict:
        return {
            "name": self.name,
            "type": self.manifest.type.value,
            "title": self.manifest.title or self.name,
            "description": self.manifest.description,
            "status": self.status.value,
            "port": self.port,
            "pid": self.pid,
            "path": self.path,
            "trusted": self.trusted,
            "sandbox": self.manifest.sandbox,
        }

    def start(self, port: int | None = None) -> int:
        if self.status == AppStatus.RUNNING:
            raise RuntimeError(f"App '{self.name}' is already running (pid={self.pid})")

        if port is not None:
            self._assigned_port = port
        elif self._assigned_port is None and self.manifest.port is not None:
            self._assigned_port = self.manifest.port

        cmd, env = self._build_launch_command()
        logger.info(f"Starting app '{self.name}': {' '.join(cmd)} in path '{self.path}'" )

        self._process = subprocess.Popen(
            cmd,
            cwd=self.path,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return self._process.pid

    def stop(self) -> bool:
        if self._process is None or self._process.poll() is not None:
            self._process = None
            return False
        logger.info(f"Stopping app '{self.name}' (pid={self._process.pid})")
        self._process.send_signal(signal.SIGTERM)
        try:
            self._process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self._process.kill()
            self._process.wait(timeout=5)
        self._process = None
        return True

    def logs(self, lines: int = 50) -> tuple[str, str]:
        if self._process is None:
            return "", ""
        stdout = ""
        stderr = ""
        if self._process.stdout and self._process.stdout.readable():
            stdout = self._process.stdout.read(4096).decode(errors="replace") if isinstance(self._process.stdout.read(0), bytes) else ""
        if self._process.stderr and self._process.stderr.readable():
            stderr = self._process.stderr.read(4096).decode(errors="replace") if isinstance(self._process.stderr.read(0), bytes) else ""
        return stdout, stderr

    def _build_launch_command(self) -> tuple[list[str], dict[str, str]]:
        env = os.environ.copy()
        env.update(self.manifest.env)

        main = self.manifest.main
        app_type = self.manifest.type

        if app_type == AppType.WEBAPP:
            main = main or "index.html"
            port = self._assigned_port or 8000
            self._assigned_port = port
            env["PORT"] = str(port)
            return ["python3", "-m", "http.server", str(port)], env

        if app_type == AppType.NODE:
            main = main or "index.js"
            if self._assigned_port:
                env["PORT"] = str(self._assigned_port)
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

        raise ValueError(f"Unknown app type: {app_type}")


def read_manifest(app_dir: str) -> GeeAppManifest | None:
    manifest_path = os.path.join(app_dir, MANIFEST_FILENAME)
    if not os.path.isfile(manifest_path):
        return None
    with open(manifest_path, "r") as f:
        data = f.read()
    return GeeAppManifest.model_validate_json(data)


def infer_manifest(app_dir: str, name: str) -> GeeAppManifest:
    if os.path.isfile(os.path.join(app_dir, "package.json")):
        main = "index.js"
        if os.path.isfile(os.path.join(app_dir, "server.js")):
            main = "server.js"
        return GeeAppManifest(name=name, type=AppType.NODE, main=main)

    if os.path.isfile(os.path.join(app_dir, "index.html")):
        return GeeAppManifest(name=name, type=AppType.WEBAPP, main="index.html")

    for ext in ("", ".exe"):
        candidate = os.path.join(app_dir, name + ext)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return GeeAppManifest(name=name, type=AppType.BINARY, main=name + ext)

    return GeeAppManifest(name=name, type=AppType.WEBAPP)


def write_manifest(app_dir: str, manifest: GeeAppManifest) -> str:
    manifest_path = os.path.join(app_dir, MANIFEST_FILENAME)
    with open(manifest_path, "w") as f:
        f.write(manifest.model_dump_json(indent=2, exclude_none=True))
    return manifest_path


class AppRegistry:
    def __init__(self):
        self._apps: dict[str, GeeApp] = {}
        self._next_port: int = 9100

    def register(self, app: GeeApp):
        self._apps[app.name] = app

    def get(self, name: str) -> GeeApp | None:
        return self._apps.get(name)

    def list(self) -> list[GeeApp]:
        return list(self._apps.values())

    def names(self) -> list[str]:
        return list(self._apps.keys())

    def unregister(self, name: str) -> bool:
        app = self._apps.pop(name, None)
        if app is not None and app.status == AppStatus.RUNNING:
            app.stop()
            return True
        return app is not None

    def stop_all(self):
        for app in self._apps.values():
            if app.status == AppStatus.RUNNING:
                app.stop()

    def start_app(self, name: str, port: int | None = None) -> GeeApp:
        app = self.get(name)
        if app is None:
            raise KeyError(f"App '{name}' not found in registry")
        if port is None:
            port = self._allocate_port()
        app.start(port=port)
        return app

    def stop_app(self, name: str) -> bool:
        app = self.get(name)
        if app is None:
            raise KeyError(f"App '{name}' not found in registry")
        return app.stop()

    def _allocate_port(self) -> int:
        port = self._next_port
        self._next_port += 1
        return port

    def load_from_directory(self, directory: str, trusted: bool = False):
        if not os.path.isdir(directory):
            logger.warning(f"App directory does not exist: {directory}")
            return

        for entry in sorted(os.listdir(directory)):
            entry_path = os.path.join(directory, entry)
            if not os.path.isdir(entry_path):
                continue

            manifest = read_manifest(entry_path)
            if manifest is None:
                manifest = infer_manifest(entry_path, entry)
                logger.debug(f"Inferred manifest for '{entry}': type={manifest.type.value}")

            app = GeeApp(name=entry, path=entry_path, manifest=manifest, trusted=trusted)
            self.register(app)
            logger.debug(f"Registered app '{entry}' ({manifest.type.value})")

        logger.info(f"Loaded {len(self._apps)} apps from {directory}")
