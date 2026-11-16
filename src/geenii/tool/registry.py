"""Tool registry and handler for Python functions and MCP tools."""

from __future__ import annotations

import inspect
import logging
import threading
from collections.abc import Callable
from typing import Any

from geenii.tool.common import Tool
from geenii.tool.mcp_tool import McpTool
from geenii.tool.python import PythonFunctionTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Central registry for discovering and invoking tools by name.

    Thread-safe: MCP server tools are added from background threads while the registry is in use.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._lock = threading.RLock()

    # -- registration -------------------------------------------------------

    def register(self, tool: Tool) -> None:
        """Register a tool instance. A tool whose name is already registered is skipped."""
        with self._lock:
            if tool.name in self._tools:
                # raise ValueError(f"Tool {tool.name!r} is already registered")
                logger.warning(f"Tool {tool.name!r} already registered")
                return
            self._tools[tool.name] = tool
        logger.info("Registered tool %r (%s)", tool.name, tool.__class__.__name__)

    def register_function(
        self,
        fn: Callable[..., Any],
        *,
        name: str | None = None,
        description: str | None = None,
        parameters: dict | None = None,
    ) -> PythonFunctionTool:
        """Convenience: wrap a plain function as a PythonTool and register it."""
        tool_name = name or fn.__name__
        tool_desc = description or (fn.__doc__ or "").strip().split("\n")[0]
        tool_params = parameters or _params_from_signature(fn)
        tool = PythonFunctionTool(
            name=tool_name,
            description=tool_desc,
            input_schema=tool_params,
            handler=fn,
        )
        self.register(tool)
        return tool

    def register_mcp_tools(
        self,
        mcp_server_id: str,
        tool_definitions: list[dict],
    ) -> list[McpTool]:
        """Register a batch of tools advertised by an MCP server.

        *tool_definitions* should be the list returned by the MCP
        ``tools/list`` method – each entry is expected to have at least
        ``name``, and optionally ``description`` and ``inputSchema``.
        """
        registered: list[McpTool] = []
        for defn in tool_definitions:
            # prefixed_name = f"{mcp_server_id}_{defn['name']}"
            tool = McpTool(
                name=defn["name"],
                mcp_server_id=mcp_server_id,
                description=defn.get("description", ""),  # .strip().split("\n")[0],
                input_schema=defn.get("input_schema", {}),
            )
            self.register(tool)
            registered.append(tool)
        return registered

    def unregister_mcp_tools(self, mcp_server_id: str) -> list[str]:
        """Remove all tools of an MCP server. Returns the removed tool names."""
        with self._lock:
            names = [
                name
                for name, tool in self._tools.items()
                if isinstance(tool, McpTool) and tool.mcp_server_id == mcp_server_id
            ]
            for name in names:
                del self._tools[name]
        return names

    def tool(
        self,
        name: str | None = None,
        *,
        description: str | None = None,
        parameters: dict | None = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """Decorator for registering a function as a tool.

        Usage::

            @registry.tool()
            def greet(name: str) -> str:
                \"\"\"Say hello.\"\"\"
                return f"Hello, {name}!"
        """

        def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
            logger.debug(f"Registering tool {name or fn.__name__!r} via fn decorator {fn.__module__}.{fn.__qualname__}")
            self.register_function(fn, name=name, description=description, parameters=parameters)
            return fn

        return decorator

    # -- lookup / removal ---------------------------------------------------

    def get(self, name: str) -> Tool:
        """Return a tool by name or raise KeyError."""
        try:
            return self._tools[name]
        except KeyError:
            raise KeyError(f"Tool {name!r} is not registered") from None

    def unregister(self, name: str) -> Tool:
        """Remove and return a tool. Raises KeyError if missing."""
        try:
            with self._lock:
                return self._tools.pop(name)
        except KeyError:
            raise KeyError(f"Tool {name!r} is not registered") from None

    def has(self, name: str) -> bool:
        return name in self._tools

    def list_tool_names(self) -> set[str]:
        """Return the names of all registered tools (insertion order)."""
        with self._lock:
            return set(self._tools.keys())

    def list_tools(self) -> list[Tool]:
        """Return all registered tools (insertion order)."""
        with self._lock:
            return list(self._tools.values())

    def list_definitions(self) -> list[dict]:
        """Return OpenAI-compatible tool definitions for all tools."""
        return [t.to_definition() for t in self.list_tools()]

    def get_tool_description(self, name: str) -> str:
        """Return a tool description by name."""
        return self._tools[name].description

    # -- invocation ---------------------------------------------------------
    # def invoke(self, name: str, args: dict, env: dict, **kwargs: Any) -> ToolCallResult:
    #     """Look up a tool by *name* and call it with *args*."""
    #     tool = self.get(name)
    #     logger.info("invoking tool %r with %s", name, args)
    #     return tool.invoke(args=args, env=env, **kwargs)
    #     #return invoke_tool(tool, args, env, **kwargs)

    # -- dunder -------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return self.has(name)

    def __repr__(self) -> str:
        names = ", ".join(self.list_tool_names())
        return f"<ToolRegistry tools=[{names}]>"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Python-type → JSON Schema type mapping (best-effort)
_TYPE_MAP: dict[type, str] = {
    str: "string",
    int: "integer",
    float: "number",
    bool: "boolean",
    list: "array",
    dict: "object",
}


def _params_from_signature(fn: Callable[..., Any]) -> dict:
    """Derive a minimal JSON-Schema ``parameters`` dict from a function signature."""
    sig = inspect.signature(fn)
    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, param in sig.parameters.items():
        if name in ("self", "cls"):
            continue
        prop: dict[str, Any] = {}
        annotation = param.annotation
        if annotation is not inspect.Parameter.empty:
            prop["type"] = _TYPE_MAP.get(annotation, "string")
        else:
            prop["type"] = "string"
        properties[name] = prop

        if param.default is inspect.Parameter.empty:
            required.append(name)

    schema: dict[str, Any] = {"type": "object", "properties": properties}
    if required:
        schema["required"] = required
    return schema
