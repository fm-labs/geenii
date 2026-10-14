import pytest

from geenii import ai
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
