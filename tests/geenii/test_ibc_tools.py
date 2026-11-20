"""Tool stubs for listings (geenii.ibc.tools): same names and schemas as the real, agent-bound tools."""

import pytest

from geenii.ibc.comms import COMMS_TOOL_NAMES, comms_tools
from geenii.ibc.tools import (
    init_builtin_comms_tools_stubs,
    init_builtin_file_tools_stubs,
    init_builtin_ibc_tools_stubs, FILE_TOOL_NAMES, files_tools,
)
from geenii.tool.common import ToolCallContext
from geenii.tool.registry import ToolRegistry


@pytest.fixture(autouse=True)
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("GEENII_HOME", str(tmp_path / "geenii-home"))


def test_comms_stubs_match_the_real_tools():
    registry = ToolRegistry()
    init_builtin_comms_tools_stubs(registry)
    assert registry.list_tool_names() == COMMS_TOOL_NAMES
    for real in comms_tools("bot"):
        stub = registry.get(real.name)
        assert (stub.description, stub.input_schema) == (real.description, real.input_schema)


def test_file_stubs_match_the_real_tools():
    registry = ToolRegistry()
    init_builtin_file_tools_stubs(registry)
    assert registry.list_tool_names() == FILE_TOOL_NAMES
    for real in files_tools("bot"):
        stub = registry.get(real.name)
        assert (stub.description, stub.input_schema) == (real.description, real.input_schema)


def test_ibc_stubs_are_all_of_them():
    registry = ToolRegistry()
    init_builtin_ibc_tools_stubs(registry)
    assert registry.list_tool_names() == COMMS_TOOL_NAMES | FILE_TOOL_NAMES


@pytest.mark.parametrize("init", [init_builtin_comms_tools_stubs, init_builtin_file_tools_stubs])
def test_calling_a_stub_is_a_tool_error(init, tmp_path):
    registry = ToolRegistry()
    init(registry)
    for tool in registry.list_tools():
        result = tool.invoke({}, ctx=ToolCallContext(cwd=str(tmp_path)))
        assert result.is_error and "only works inside an agent" in result.text
