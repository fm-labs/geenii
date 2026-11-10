from __future__ import annotations

import json
from typing import Any
from mcp.types import CallToolResult, TextContent

from geenii.mcp_config import get_mcp_client_for_server
from geenii.mcp_client import McpClient
from geenii.tool.common import Tool, ToolCallResult, ToolCallContext


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

    def invoke(
        self,
        args: dict[str, Any],
        env: dict[str, str] | None = None,
        *,
        ctx: ToolCallContext,
    ) -> ToolCallResult:
        try:
            client: McpClient = get_mcp_client_for_server(self.mcp_server_id)
            result = client.call_tool(self._mcp_fn_name, args=args)
        except Exception as e:
            result = e

        if isinstance(result, Exception):
            return ToolCallResult(
                text=str(result),
                structured_content={"error": str(result)},
                is_error=True,
            )

        text, data, is_error = "", None, False
        if isinstance(result, CallToolResult):
            if result.content and len(result.content) > 0:
                if isinstance(result.content[0], TextContent):
                    text = result.content[0].text
            if result.structured_content:
                data = result.structured_content
            elif len(text) > 0:  # and result.is_error == False
                # attempt to parse text as json
                try:
                    data = json.loads(text)
                except json.JSONDecodeError:
                    pass
            is_error = result.is_error
        else:
            text = "Unknown result type"
            is_error = True

        # print(text, data, is_error)
        return ToolCallResult(text, structured_content=data, is_error=is_error)
