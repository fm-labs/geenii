import logging
from logging.handlers import RotatingFileHandler

import pytest
from click.testing import CliRunner

from geenii import logs


@pytest.fixture
def root_logging(monkeypatch, tmp_path):
    """Isolate root logger changes and send log files to tmp_path."""
    monkeypatch.setattr(logs, "GEENII_CACHE_DIR", str(tmp_path))
    monkeypatch.delenv("GEENII_LOG_NAME", raising=False)
    monkeypatch.setenv("GEENII_LOGGING", "plain")
    root = logging.getLogger()
    saved_handlers, saved_level = root.handlers[:], root.level
    # Note: pytest's own capture handlers sit on the root logger while a test runs,
    # so the tests configure with force=True wherever they need a fresh setup.
    yield root
    for h in root.handlers:
        if h not in saved_handlers:
            h.close()
    root.handlers, root.level = saved_handlers, saved_level


def _log_files(root) -> list[str]:
    return [h.baseFilename for h in root.handlers if isinstance(h, RotatingFileHandler)]


def test_resolve_log_name(monkeypatch):
    monkeypatch.delenv("GEENII_LOG_NAME", raising=False)
    assert logs.resolve_log_name() == "geenii"
    assert logs.resolve_log_name("geenii-agent") == "geenii-agent"
    monkeypatch.setenv("GEENII_LOG_NAME", "agent-dice")
    assert logs.resolve_log_name("geenii-agent") == "agent-dice"


def test_resolve_log_name_stays_inside_logs_dir(monkeypatch):
    monkeypatch.setenv("GEENII_LOG_NAME", "../../etc/x")
    name = logs.resolve_log_name()
    assert "/" not in name and not name.startswith(".")


def test_init_logging_uses_log_name(root_logging, tmp_path):
    logs.init_logging("geenii-agent", force=True)
    assert _log_files(root_logging) == [str(tmp_path / "logs" / "geenii-agent.log")]


def test_init_logging_env_overrides_log_name(root_logging, tmp_path, monkeypatch):
    monkeypatch.setenv("GEENII_LOG_NAME", "agent-dice")
    logs.init_logging("geenii-agent", force=True)
    assert _log_files(root_logging) == [str(tmp_path / "logs" / "agent-dice.log")]


def test_init_logging_force_replaces_handlers(root_logging, tmp_path):
    logs.init_logging("first", force=True)
    logs.init_logging("second")  # no-op: already configured
    assert _log_files(root_logging) == [str(tmp_path / "logs" / "first.log")]
    logs.init_logging("second", force=True)
    assert _log_files(root_logging) == [str(tmp_path / "logs" / "second.log")]


def test_cli_logs_to_a_file_per_command(root_logging, tmp_path):
    from geenii.cli.main import geecli

    result = CliRunner().invoke(geecli, ["pm", "--help"])
    assert result.exit_code == 0, result.output
    assert _log_files(root_logging) == [str(tmp_path / "logs" / "geenii-pm.log")]
