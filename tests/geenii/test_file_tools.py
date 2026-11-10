import os

import pytest

from geenii import config
from geenii.tool.common import ToolCallContext
from geenii.tool.computer import ReadTool, WriteTool


@pytest.fixture
def dirs(tmp_path, monkeypatch):
    """A working dir, a separate GEENII_WORKING_DIR, an outside dir, and no allowed_dirs in the user settings."""
    d = {name: tmp_path / name for name in ("wd", "geenii_wd", "outside", "extra")}
    for p in d.values():
        p.mkdir()
    monkeypatch.setattr(config, "GEENII_WORKING_DIR", str(d["geenii_wd"]))
    monkeypatch.setattr(config, "read_user_settings", dict)
    return d


@pytest.fixture
def ctx(dirs):
    return ToolCallContext(cwd=str(dirs["wd"]))


def read(ctx, file_path):
    return ReadTool().invoke(args={"file_path": file_path}, ctx=ctx)


def write(ctx, file_path, contents="data"):
    return WriteTool().invoke(
        args={"file_path": file_path, "contents": contents}, ctx=ctx
    )


def test_names():
    assert ReadTool().name == "read"
    assert WriteTool().name == "write"


# ---------- read ----------


def test_read_relative_path(dirs, ctx):
    (dirs["wd"] / "a.txt").write_text("hello")
    result = read(ctx, "a.txt")
    assert result.is_error is False
    assert result.text == "hello"


def test_read_relative_path_in_subdir(dirs, ctx):
    (dirs["wd"] / "sub").mkdir()
    (dirs["wd"] / "sub" / "a.txt").write_text("nested")
    assert read(ctx, "sub/a.txt").text == "nested"


def test_read_absolute_path(dirs, ctx):
    (dirs["wd"] / "a.txt").write_text("hello")
    assert read(ctx, str(dirs["wd"] / "a.txt")).text == "hello"


def test_read_in_geenii_working_dir(dirs, ctx):
    (dirs["geenii_wd"] / "a.txt").write_text("global")
    assert read(ctx, str(dirs["geenii_wd"] / "a.txt")).text == "global"


def test_read_outside_allowed_dirs_is_rejected(dirs, ctx):
    (dirs["outside"] / "secret.txt").write_text("secret")
    result = read(ctx, str(dirs["outside"] / "secret.txt"))
    assert result.is_error is True
    assert "not allowed" in result.text
    assert result.text != "secret"


@pytest.mark.parametrize(
    "path", ["../outside/secret.txt", "sub/../../outside/secret.txt"]
)
def test_read_dotdot_escape_is_rejected(dirs, ctx, path):
    (dirs["wd"] / "sub").mkdir()
    (dirs["outside"] / "secret.txt").write_text("secret")
    result = read(ctx, path)
    assert result.is_error is True
    assert "not allowed" in result.text


def test_read_dotdot_that_stays_inside_is_allowed(dirs, ctx):
    (dirs["wd"] / "sub").mkdir()
    (dirs["wd"] / "a.txt").write_text("hello")
    assert read(ctx, "sub/../a.txt").text == "hello"


def test_read_symlink_escape_is_rejected(dirs, ctx):
    (dirs["outside"] / "secret.txt").write_text("secret")
    os.symlink(dirs["outside"] / "secret.txt", dirs["wd"] / "link.txt")
    result = read(ctx, "link.txt")
    assert result.is_error is True
    assert "not allowed" in result.text


def test_read_working_dir_itself_is_rejected(dirs, ctx):
    result = read(ctx, ".")
    assert result.is_error is True
    assert "not allowed" in result.text


def test_read_in_allowed_dirs_from_user_settings(dirs, ctx, monkeypatch):
    (dirs["extra"] / "a.txt").write_text("extra")
    assert read(ctx, str(dirs["extra"] / "a.txt")).is_error is True

    monkeypatch.setattr(
        config, "read_user_settings", lambda: {"allowed_dirs": [str(dirs["extra"])]}
    )
    assert read(ctx, str(dirs["extra"] / "a.txt")).text == "extra"


def test_allowed_dirs_that_is_not_a_list_is_ignored(dirs, ctx, monkeypatch):
    (dirs["extra"] / "a.txt").write_text("extra")
    monkeypatch.setattr(
        config, "read_user_settings", lambda: {"allowed_dirs": str(dirs["extra"])}
    )
    assert read(ctx, str(dirs["extra"] / "a.txt")).is_error is True


def test_read_missing_file_is_an_error(ctx):
    result = read(ctx, "missing.txt")
    assert result.is_error is True


@pytest.mark.parametrize(
    "args", [{}, {"file_path": ""}, {"file_path": None}, {"file_path": 5}]
)
def test_read_invalid_file_path_is_an_error(ctx, args):
    result = ReadTool().invoke(args=args, ctx=ctx)
    assert result.is_error is True
    assert "Invalid file_path" in result.text


# ---------- write ----------


def test_write_relative_path(dirs, ctx):
    result = write(ctx, "a.txt", "hello")
    assert result.is_error is False
    assert (dirs["wd"] / "a.txt").read_text() == "hello"
    assert str(os.path.realpath(dirs["wd"] / "a.txt")) in result.text


def test_write_absolute_path(dirs, ctx):
    assert write(ctx, str(dirs["wd"] / "a.txt"), "hello").is_error is False
    assert (dirs["wd"] / "a.txt").read_text() == "hello"


def test_write_overwrites(dirs, ctx):
    (dirs["wd"] / "a.txt").write_text("old")
    write(ctx, "a.txt", "new")
    assert (dirs["wd"] / "a.txt").read_text() == "new"


def test_write_without_contents_writes_an_empty_file(dirs, ctx):
    result = WriteTool().invoke(args={"file_path": "a.txt"}, ctx=ctx)
    assert result.is_error is False
    assert (dirs["wd"] / "a.txt").read_text() == ""


def test_write_outside_allowed_dirs_is_rejected(dirs, ctx):
    result = write(ctx, str(dirs["outside"] / "a.txt"))
    assert result.is_error is True
    assert "not allowed" in result.text
    assert not (dirs["outside"] / "a.txt").exists()


@pytest.mark.parametrize("path", ["../outside/a.txt", "sub/../../outside/a.txt"])
def test_write_dotdot_escape_is_rejected(dirs, ctx, path):
    (dirs["wd"] / "sub").mkdir()
    result = write(ctx, path)
    assert result.is_error is True
    assert "not allowed" in result.text
    assert not (dirs["outside"] / "a.txt").exists()


def test_write_through_symlinked_dir_is_rejected(dirs, ctx):
    os.symlink(dirs["outside"], dirs["wd"] / "linkdir")
    result = write(ctx, "linkdir/a.txt")
    assert result.is_error is True
    assert not (dirs["outside"] / "a.txt").exists()


def test_write_in_allowed_dirs_from_user_settings(dirs, ctx, monkeypatch):
    monkeypatch.setattr(
        config, "read_user_settings", lambda: {"allowed_dirs": [str(dirs["extra"])]}
    )
    assert write(ctx, str(dirs["extra"] / "a.txt"), "extra").is_error is False
    assert (dirs["extra"] / "a.txt").read_text() == "extra"


def test_write_into_missing_dir_is_an_error(dirs, ctx):
    result = write(ctx, "missing/a.txt")
    assert result.is_error is True
    assert not (dirs["wd"] / "missing").exists()


@pytest.mark.parametrize(
    "args",
    [
        {"contents": "x"},
        {"file_path": "", "contents": "x"},
        {"file_path": None, "contents": "x"},
        {"file_path": 5, "contents": "x"},
    ],
)
def test_write_invalid_file_path_is_an_error(ctx, args):
    result = WriteTool().invoke(args=args, ctx=ctx)
    assert result.is_error is True
    assert "Invalid file_path" in result.text
