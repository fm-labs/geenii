"""
Per-agent environment variables and secrets.

Each agent has two dotenv files in the user's agent directory (whatever the agent's scope, so a committed
project directory never holds them):

- ``<name>.vars.env``    plain environment variables
- ``<name>.secrets.env`` sensitive environment variables (file mode 0600, values are never returned by the API)

Secrets are stored as plain text for now. Encryption would only change ``_read_secrets`` / ``_write_secrets``.
"""

import logging
import os
import re
import tempfile
from pathlib import Path

import dotenv

from geenii.utils.os_util import get_user_home_dir

logger = logging.getLogger(__name__)

ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def validate_env_key(key: str) -> None:
    if not ENV_KEY_PATTERN.match(key or ""):
        raise ValueError(f"Invalid environment variable name '{key}'.")


class AgentEnvStore:
    def __init__(self, base_dir: str | Path | None = None):
        self.base_dir = Path(base_dir) if base_dir else Path(get_user_home_dir()) / ".geenii" / "agents"

    def vars_path(self, agent: str) -> Path:
        return self.base_dir / f"{agent}.vars.env"

    def secrets_path(self, agent: str) -> Path:
        return self.base_dir / f"{agent}.secrets.env"

    # vars

    def get_vars(self, agent: str) -> dict[str, str]:
        return self._read(self.vars_path(agent))

    def set_vars(self, agent: str, values: dict[str, str]) -> None:
        """Replace all vars of the agent."""
        for key in values:
            validate_env_key(key)
        self._write(self.vars_path(agent), values)

    def set_var(self, agent: str, key: str, value: str) -> None:
        self.set_vars(agent, {**self.get_vars(agent), key: value})

    def delete_var(self, agent: str, key: str) -> bool:
        values = self.get_vars(agent)
        if key not in values:
            return False
        del values[key]
        self.set_vars(agent, values)
        return True

    # secrets

    def get_secrets(self, agent: str) -> dict[str, str]:
        return self._read(self.secrets_path(agent))

    def secret_keys(self, agent: str) -> list[str]:
        return list(self.get_secrets(agent).keys())

    def set_secret(self, agent: str, key: str, value: str) -> None:
        validate_env_key(key)
        self._write(
            self.secrets_path(agent),
            {**self.get_secrets(agent), key: value},
            mode=0o600,
        )

    def delete_secret(self, agent: str, key: str) -> bool:
        values = self.get_secrets(agent)
        if key not in values:
            return False
        del values[key]
        self._write(self.secrets_path(agent), values, mode=0o600)
        return True

    def resolve(self, agent: str) -> dict[str, str]:
        """The agent's environment: vars, with secrets on top."""
        return {**self.get_vars(agent), **self.get_secrets(agent)}

    # file io

    @staticmethod
    def _read(path: Path) -> dict[str, str]:
        if not path.is_file():
            return {}
        try:
            return {k: v or "" for k, v in dotenv.dotenv_values(path).items()}
        except Exception as e:
            logger.error(f"Could not read env file '{path}': {e}")
            return {}

    @staticmethod
    def _write(path: Path, values: dict[str, str], mode: int = 0o644) -> None:
        """Writes the file atomically. An empty dict removes the file."""
        if not values:
            path.unlink(missing_ok=True)
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
        try:
            os.chmod(tmp, mode)
            with os.fdopen(fd, "w") as f:
                for key, value in values.items():
                    f.write(f"{key}={_quote(value)}\n")
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise


def _quote(value: str) -> str:
    # single quotes are taken literally by python-dotenv, unless the value contains one itself
    if "'" not in value and "\n" not in value:
        return f"'{value}'"
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'
