import json

import pytest

from geenii import mcp_config as mc


class FakeClient:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


# ---------- env var expansion ----------


def expand(cfg, env_vars):
    return mc._expand_env_vars_in_server_config(cfg, env_vars)


def test_expands_command_and_url():
    cfg = expand(
        {"command": "${BIN}/run", "url": "http://${HOST}:8000/mcp"},
        {"BIN": "/usr/bin", "HOST": "localhost"},
    )
    assert cfg == {"command": "/usr/bin/run", "url": "http://localhost:8000/mcp"}


def test_expands_each_arg():
    cfg = expand(
        {
            "command": "docker",
            "args": ["run", "-e", "TOKEN=${TOKEN}", "${IMAGE}:${TAG}"],
        },
        {"TOKEN": "abc", "IMAGE": "mcp/x", "TAG": "1.0"},
    )
    assert cfg["args"] == ["run", "-e", "TOKEN=abc", "mcp/x:1.0"]


def test_expands_env_and_header_values_not_keys():
    cfg = expand(
        {
            "env": {"API_KEY": "${KEY}"},
            "headers": {"Authorization": "Bearer ${KEY}", "${KEY}": "x"},
        },
        {"KEY": "secret"},
    )
    assert cfg["env"] == {"API_KEY": "secret"}
    assert cfg["headers"] == {"Authorization": "Bearer secret", "${KEY}": "x"}


def test_unknown_variable_is_left_as_is():
    cfg = expand({"url": "http://${HOST}/${MISSING}"}, {"HOST": "h"})
    assert cfg["url"] == "http://h/${MISSING}"


@pytest.mark.parametrize("value", ["$HOST", "${HOST", "{HOST}", "${}", "${HOST-NAME}"])
def test_only_braced_word_names_are_expanded(value):
    assert expand({"url": value}, {"HOST": "h", "HOST-NAME": "x"})["url"] == value


def test_non_string_values_and_other_keys_are_untouched():
    cfg = expand(
        {
            "command": "x",
            "args": ["${A}", 3, None],
            "env": {"N": 1},
            "cwd": "${A}",
            "timeout": 5,
        },
        {"A": "a"},
    )
    assert cfg == {
        "command": "x",
        "args": ["a", 3, None],
        "env": {"N": 1},
        "cwd": "${A}",
        "timeout": 5,
    }


def test_missing_keys_are_not_added():
    assert expand({"url": "http://x"}, {}) == {"url": "http://x"}


def test_value_is_inserted_literally():
    # a value containing a placeholder or regex escapes is not expanded again
    cfg = expand({"url": "${A}"}, {"A": "${B}\\1", "B": "b"})
    assert cfg["url"] == "${B}\\1"


# ---------- reading ----------


def test_project_file_overrides_root(mcp_dirs):
    root, project = mcp_dirs
    write_json(
        root,
        {
            "env": {"A": "root", "B": "root"},
            "mcpServers": {"x": {"command": "root"}, "y": {"command": "y"}},
        },
    )
    write_json(project, {"env": {"A": "project"}, "mcpServers": {"x": {"command": "project"}}})

    cfg = mc.get_mcp_config()

    assert cfg["mcpServers"] == {"x": {"command": "project"}, "y": {"command": "y"}}
    assert cfg["env"] == {"A": "project", "B": "root"}


def test_missing_and_invalid_files_are_skipped(mcp_dirs):
    _root, project = mcp_dirs
    project.parent.mkdir(parents=True)
    project.write_text("{not json")

    assert mc.read_mcp_config_files() == {"mcpServers": {}, "env": {}}


def test_compiled_server_config_is_a_copy(mcp_dirs):
    root, _ = mcp_dirs
    write_json(
        root,
        {
            "env": {"TOKEN": "abc"},
            "mcpServers": {
                "x": {
                    "url": "http://h",
                    "headers": {"Authorization": "Bearer ${TOKEN}"},
                }
            },
        },
    )

    compiled = mc.get_mcp_config_for_server("x", compile=True)

    assert compiled["headers"] == {"Authorization": "Bearer abc"}
    # the cached config keeps the placeholder
    assert mc.get_mcp_config_for_server("x")["headers"] == {"Authorization": "Bearer ${TOKEN}"}


def test_unknown_server_is_none(mcp_dirs):
    assert mc.get_mcp_config_for_server("nope") is None
    assert mc.get_mcp_config_for_server("nope", compile=True) is None


# ---------- writing ----------


def test_read_root_config_of_missing_file(mcp_dirs):
    assert mc.read_root_mcp_config() == {"mcpServers": {}}


def test_read_root_config_rejects_non_object(mcp_dirs):
    root, _ = mcp_dirs
    write_json(root, ["x"])
    with pytest.raises(ValueError):
        mc.read_root_mcp_config()


def test_save_creates_root_file(mcp_dirs):
    root, project = mcp_dirs

    mc.save_mcp_server_config("x", {"url": "http://h/${TOKEN}"})

    assert json.loads(root.read_text()) == {"mcpServers": {"x": {"url": "http://h/${TOKEN}"}}}
    assert not project.exists()
    assert not root.with_name("mcp.json.tmp").exists()


def test_save_keeps_other_entries_and_keys(mcp_dirs):
    root, _ = mcp_dirs
    write_json(
        root,
        {
            "env": {"A": "a"},
            "other": 1,
            "mcpServers": {"keep": {"command": "k"}, "x": {"command": "old"}},
        },
    )

    mc.save_mcp_server_config("x", {"command": "new"})

    assert json.loads(root.read_text()) == {
        "env": {"A": "a"},
        "other": 1,
        "mcpServers": {"keep": {"command": "k"}, "x": {"command": "new"}},
    }


def test_save_reloads_config_and_drops_cached_client(mcp_dirs):
    mc.get_mcp_config()
    client = FakeClient()
    mc._client_cache["x"] = client

    mc.save_mcp_server_config("x", {"command": "new"})

    assert mc.get_mcp_config_for_server("x") == {"command": "new"}
    assert client.closed
    assert "x" not in mc._client_cache


def test_delete(mcp_dirs):
    root, _ = mcp_dirs
    write_json(root, {"mcpServers": {"keep": {"command": "k"}, "x": {"command": "x"}}})
    client = FakeClient()
    mc._client_cache["x"] = client

    assert mc.delete_mcp_server_config("x") is True

    assert json.loads(root.read_text()) == {"mcpServers": {"keep": {"command": "k"}}}
    assert mc.get_mcp_config_for_server("x") is None
    assert client.closed


def test_delete_unknown_server(mcp_dirs):
    root, _ = mcp_dirs
    assert mc.delete_mcp_server_config("nope") is False
    assert not root.exists()


def test_delete_ignores_project_only_server(mcp_dirs):
    _, project = mcp_dirs
    write_json(project, {"mcpServers": {"x": {"command": "x"}}})

    assert mc.delete_mcp_server_config("x") is False
    assert json.loads(project.read_text()) == {"mcpServers": {"x": {"command": "x"}}}
