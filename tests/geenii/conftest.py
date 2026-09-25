import pytest

from geenii.pm import process_manager as pm_mod


@pytest.fixture(autouse=True)
def isolated_processes_dir(tmp_path, monkeypatch):
    """Keep process records of default-constructed ProcessManagers out of the real cache dir."""
    path = tmp_path / "default-processes"
    monkeypatch.setattr(pm_mod, "PROCESSES_DIR", str(path))
    return path
