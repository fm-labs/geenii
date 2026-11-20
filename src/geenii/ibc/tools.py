"""Stubs of the IBC tools, for tool listings (e.g. the server's GET /tools/).

The real tools are bound to one agent (and its working folder), so they are created per agent by
comms_tools() and files_tools() when its spec lists them. The stubs share their names, descriptions and
parameters (COMMS_TOOL_DEFS, FILE_TOOL_DEFS); calling one returns a tool error.
"""

from __future__ import annotations

from typing import Any

from geenii.ibc.comms import COMMS_TOOL_DEFS
from geenii.ibc.files import FILE_TOOL_DEFS
from geenii.tool.registry import ToolRegistry


def _stub(name: str):
    def stub(**kwargs) -> Any:
        raise RuntimeError(f"Tool {name!r} only works inside an agent; list it in the agent's tools")

    stub.__name__ = name
    return stub


def _register_stubs(registry: ToolRegistry, defs: dict[str, tuple[str, dict]]) -> None:
    for name, (description, parameters) in defs.items():
        registry.register_function(_stub(name), name=name, description=description, parameters=parameters)


def init_builtin_comms_tools_stubs(registry: ToolRegistry) -> None:
    """Register stubs of the agent mail and blackboard tools (see comms_tools())."""
    _register_stubs(registry, COMMS_TOOL_DEFS)


def init_builtin_file_tools_stubs(registry: ToolRegistry) -> None:
    """Register stubs of the file store tools (see files_tools())."""
    _register_stubs(registry, FILE_TOOL_DEFS)


def init_builtin_ibc_tools_stubs(registry: ToolRegistry) -> None:
    """Register stubs of all IBC tools: mail, blackboard and file store."""
    init_builtin_comms_tools_stubs(registry)
    init_builtin_file_tools_stubs(registry)
