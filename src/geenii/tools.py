"""Tool registry and handler for Python functions and MCP tools."""

from __future__ import annotations

import inspect
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable

from fastmcp import Client

from geenii.mcp.client import get_mcp_client_for_server, McpClient

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class Tool(ABC):
    """Abstract base for all tool types."""

    def __init__(self, name: str, description: str = "", parameters: dict | None = None):
        self.name = name
        self.description = description
        self.parameters = parameters or {}

    #def __str__(self) -> str:
    #    return self.name

    #def __repr__(self) -> str:
    #    return f"<{self.__class__.__name__} name={self.name!r}>"

    @abstractmethod
    def invoke(self, **kwargs: Any) -> Any:
        ...

    def to_definition(self) -> dict:
        """Return an OpenAI-compatible tool definition."""
        return {
            "type": "function",
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


    def to_ollama(self) -> dict:
        """Return an OpenAI-compatible tool definition."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# ---------------------------------------------------------------------------
# Python tool
# ---------------------------------------------------------------------------


class PythonTool(Tool):
    """A tool backed by a plain Python callable."""

    def __init__(
        self,
        name: str,
        description: str = "",
        parameters: dict | None = None,
        handler: Callable[..., Any] | None = None,
    ):
        super().__init__(name, description, parameters)
        self.handler = handler

    def invoke(self, **kwargs: Any) -> Any:
        if self.handler is None:
            raise RuntimeError(f"No handler registered for tool {self.name!r}")
        return self.handler(**kwargs)


# ---------------------------------------------------------------------------
# MCP tool
# ---------------------------------------------------------------------------


class McpTool(Tool):
    """A tool whose execution is delegated to an MCP server."""

    def __init__(
        self,
        name: str,
        mcp_server_id: str,
        description: str = "",
        parameters: dict | None = None,
    ):
        super().__init__(name, description, parameters)
        self._name = name
        self.name = f"{mcp_server_id}_{name}"
        self.mcp_server_id = mcp_server_id

    def invoke(self, **kwargs: Any) -> Any:
        client: McpClient = get_mcp_client_for_server(self.mcp_server_id)

        return client.call_tool_sync(self._name, args=kwargs)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


class ToolRegistry:
    """Central registry for discovering and invoking tools by name."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    # -- registration -------------------------------------------------------

    def register(self, tool: Tool) -> None:
        """Register a tool instance. Raises ValueError on duplicate names."""
        if tool.name in self._tools:
            raise ValueError(f"Tool {tool.name!r} is already registered")
        self._tools[tool.name] = tool
        logger.debug("registered tool %r (%s)", tool.name, tool.__class__.__name__)

    def register_function(
        self,
        fn: Callable[..., Any],
        *,
        name: str | None = None,
        description: str | None = None,
        parameters: dict | None = None,
    ) -> PythonTool:
        """Convenience: wrap a plain function as a PythonTool and register it."""
        tool_name = name or fn.__name__
        tool_desc = description or (fn.__doc__ or "").strip().split("\n")[0]
        tool_params = parameters or _params_from_signature(fn)
        tool = PythonTool(
            name=tool_name,
            description=tool_desc,
            parameters=tool_params,
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
            #prefixed_name = f"{mcp_server_id}_{defn['name']}"
            tool = McpTool(
                name=defn['name'],
                mcp_server_id=mcp_server_id,
                description=defn.get("description", "").strip().split("\n")[0],
                parameters=defn.get("inputSchema", {}),
            )
            self.register(tool)
            registered.append(tool)
        return registered

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
            print(f"Registering tool {name or fn.__name__!r} from function {fn.__module__}.{fn.__qualname__}")
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
            return self._tools.pop(name)
        except KeyError:
            raise KeyError(f"Tool {name!r} is not registered") from None

    def has(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self) -> list[Tool]:
        """Return all registered tools (insertion order)."""
        return list(self._tools.values())

    def list_definitions(self) -> list[dict]:
        """Return OpenAI-compatible tool definitions for all tools."""
        return [t.to_definition() for t in self._tools.values()]

    # -- invocation ---------------------------------------------------------

    def invoke(self, name: str, **kwargs: Any) -> Any:
        """Look up a tool by *name* and call it with *kwargs*."""
        tool = self.get(name)
        logger.debug("invoking tool %r with %s", name, kwargs)
        return tool.invoke(**kwargs)

    # -- dunder -------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._tools)

    def __contains__(self, name: str) -> bool:
        return self.has(name)

    def __repr__(self) -> str:
        names = ", ".join(self._tools)
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
