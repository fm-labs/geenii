"""Stubs of the IBC tools, for tool listings (e.g. the server's GET /tools/).

The real tools are bound to one agent (and its working folder), so they are created per agent by
comms_tools() and files_tools() when its spec lists them. The stubs share their names, descriptions and
parameters (COMMS_TOOL_DEFS, FILE_TOOL_DEFS); calling one returns a tool error.
"""

from __future__ import annotations

import os
from pathlib import Path

from typing import Any

from geenii.ibc.comms import COMMS_TOOL_DEFS, MAX_TEXT, check_agent_name
from geenii.ibc.filestore import FileStore
from geenii.tool.registry import ToolRegistry
from geenii.utils.schema import string, params, boolean


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


# -- tools bound to one agent ---------------------------------------------------

_FILE_ID_PARAM = string("File id, e.g. f_3f9c...")

# name -> (description, parameters) of the file tools; shared by files_tools() and the stubs
FILE_TOOL_DEFS: dict[str, tuple[str, dict]] = {
    "filestore_upload": (
        "Upload a file from your working folder to the shared file store. Returns its id, which you can "
        "attach to agent mail (agentmail_send attachments) or mention to other agents.",
        params(
            path=string("File path, relative to your working folder"),
            note=string("Optional short description"),
            required=["path"],
        ),
    ),
    "filestore_download": (
        "Copy a file from the shared file store into your working folder.",
        params(
            file_id=_FILE_ID_PARAM,
            path=string("Where to save it, relative to your working folder (default: its own name)"),
            overwrite=boolean("Replace an existing file, default false"),
            required=["file_id"],
        ),
    ),
    "filestore_list": (
        "List your filebox: the files you uploaded and the files other agents shared with you.",
        params(),
    ),
    "filestore_info": (
        "Show a stored file's name, size, type, owner and note, without its content.",
        params(file_id=_FILE_ID_PARAM, required=["file_id"]),
    ),
    "filestore_save_text": (
        "Save text as a new file in the shared file store (no working folder needed). Returns its id.",
        params(
            name=string("File name, e.g. report.md"),
            text=string("The file content"),
            note=string("Optional short description"),
            required=["name", "text"],
        ),
    ),
    "filestore_read_text": (
        f"Read a stored text file (up to {MAX_TEXT} characters). For binary or longer files use filestore_download.",
        params(file_id=_FILE_ID_PARAM, required=["file_id"]),
    ),
}
FILE_TOOL_NAMES = frozenset(FILE_TOOL_DEFS)


def files_tools(agent_name: str, store: FileStore | None = None):
    """The file store tools for one agent. Uploads are owned by `agent_name`; paths are relative to the agent's
    working folder and must pass the same checks as the `read` and `write` tools."""
    from geenii.tool.common import ToolCallContext, to_tool_call_result
    from geenii.tool.computer import _normalize_path, is_file_in_allowed_dirs
    from geenii.tool.python import PythonFunctionTool

    check_agent_name(agent_name)
    store = store or FileStore()

    class AgentFileTool(PythonFunctionTool):
        """A function tool whose handler also gets the agent's working folder as `cwd`."""

        def invoke(self, args, env=None, *, ctx: ToolCallContext):
            try:
                return to_tool_call_result(self.handler(cwd=ctx.cwd, **args))
            except Exception as e:
                return to_tool_call_result(e)

    def _allowed(path: str, cwd: str | None, what: str) -> Path:
        base = cwd or os.getcwd()
        resolved = _normalize_path(path, base)
        if not is_file_in_allowed_dirs(resolved, base):
            raise ValueError(f"You are not allowed to {what} this file: {resolved}")
        return Path(resolved)

    def _summary(meta: dict) -> dict:
        return {k: meta.get(k) for k in ("id", "name", "size", "mime", "owner", "created_at", "note")}

    def filestore_upload(path: str, note: str = "", cwd: str | None = None) -> dict:
        return _summary(store.put(agent_name, _allowed(path, cwd, "upload"), note=note))

    def filestore_download(file_id: str, path: str = "", overwrite: bool = False, cwd: str | None = None) -> dict:
        meta = store.info(file_id)
        dest = _allowed(path or meta["name"], cwd, "write")
        dest = store.copy_to(file_id, dest, overwrite=bool(overwrite))
        if not is_file_in_allowed_dirs(dest, cwd or os.getcwd()):  # a directory DEST got the file's name
            dest.unlink(missing_ok=True)
            raise ValueError(f"You are not allowed to write this file: {dest}")
        return {"saved": str(dest), "id": meta["id"], "name": meta["name"], "size": meta["size"]}

    def filestore_list(cwd: str | None = None) -> dict:
        files = store.list(agent_name)
        return (
            {"files": [_summary(m) | {"shared": m.get("owner") != agent_name} for m in files]}
            if files
            else {"files": [], "note": "Your filebox is empty."}
        )

    def filestore_info(file_id: str, cwd: str | None = None) -> dict:
        meta = store.info(file_id)
        return _summary(meta) | {"sha256": meta["sha256"], "shared_with": meta.get("shared_with", [])}

    def filestore_save_text(name: str, text: str, note: str = "", cwd: str | None = None) -> dict:
        return _summary(store.put_text(agent_name, name, text, note=note))

    def filestore_read_text(file_id: str, cwd: str | None = None) -> dict:
        meta = store.info(file_id)
        text, truncated = store.read_text(file_id)
        result = {"id": meta["id"], "name": meta["name"], "text": text}
        if truncated:
            result["truncated"] = f"Only the first {len(text)} characters; download the file for all of it."
        return result

    handlers = {
        "filestore_upload": filestore_upload,
        "filestore_download": filestore_download,
        "filestore_list": filestore_list,
        "filestore_info": filestore_info,
        "filestore_save_text": filestore_save_text,
        "filestore_read_text": filestore_read_text,
    }
    return [
        AgentFileTool(name, description, parameters, handlers[name])
        for name, (description, parameters) in FILE_TOOL_DEFS.items()
    ]
