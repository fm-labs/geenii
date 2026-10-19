import pytest

from geenii import ai
from geenii import mcp_config
from geenii.pm import process_manager as pm_mod


@pytest.fixture(autouse=True)
def isolated_ai_logs(tmp_path, monkeypatch):
    """Keep the completion and usage logs of test calls out of the real cache dir."""
    path = tmp_path / "ai-cache"
    monkeypatch.setattr(ai, "CACHE_DIR", str(path))
    return path


@pytest.fixture(autouse=True)
def isolated_processes_dir(tmp_path, monkeypatch):
    """Keep process records of default-constructed ProcessManagers out of the real cache dir."""
    path = tmp_path / "default-processes"
    monkeypatch.setattr(pm_mod, "PROCESSES_DIR", str(path))
    return path


@pytest.fixture
def mcp_dirs(tmp_path, monkeypatch):
    """Point the root (user home) and project mcp.json at temp dirs, with empty caches. Returns both paths."""
    home = tmp_path / "home"
    project = tmp_path / "project"
    monkeypatch.setattr(mcp_config, "get_user_home_dir", lambda: str(home))
    monkeypatch.setattr(mcp_config, "GEENII_WORKING_DIR", str(project))
    monkeypatch.setattr(mcp_config, "config", None)
    monkeypatch.setattr(mcp_config, "_client_cache", {})
    return home / ".geenii" / "mcp.json", project / ".geenii" / "mcp.json"
