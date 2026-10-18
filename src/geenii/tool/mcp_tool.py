from __future__ import annotations

import json
from typing import Any
from mcp.types import CallToolResult, TextContent

from geenii.mcp_config import get_mcp_client_for_server
from geenii.mcp_client import McpClient
from geenii.tool.common import Tool, ToolCallResult


class McpTool(Tool):
    """A tool whose execution is delegated to an MCP server."""

    def __init__(
        self,
        name: str,
        mcp_server_id: str,
        description: str = "",
        input_schema: dict | None = None,
    ):
        super().__init__(name, description, input_schema)
        self._mcp_fn_name = name
        self.name = f"mcp__{mcp_server_id}__{name}"
        self.mcp_server_id = mcp_server_id
        self.type = "mcp_tool"

    def invoke(self, args: dict[str,Any], env: dict[str, str] | None = None, **kwargs: Any) -> ToolCallResult:
        try:
            client: McpClient = get_mcp_client_for_server(self.mcp_server_id)
            result = client.call_tool(self._mcp_fn_name, args=args)
        except Exception as e:
            print("MCP tool error:", e)
            result = e
            raise e

        if isinstance(result, Exception):
            print("MCP tool exception:", result)
            return ToolCallResult(text=str(result), structured_content=None, is_error=True)

        text = ""
        data = None
        is_error = False
        if isinstance(result, CallToolResult):
            if result.content and len(result.content) > 0:
                if isinstance(result.content[0], TextContent):
                    text = result.content[0].text
            if result.structured_content:
                data = result.structured_content
            elif len(text) > 0:
                # attempt to parse text as json
                try:
                    data = json.loads(text)
                except Exception:
                    pass
        else:
            is_error = True
            text = "Unknown error during tool invocation: Unknown result type"

        return ToolCallResult(text, structured_content=data, is_error=is_error)
