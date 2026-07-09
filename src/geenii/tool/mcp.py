from __future__ import annotations

from typing import Any

from geenii.mcp import McpClient, get_mcp_client_for_server
from geenii.tool.common import Tool


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
        self._mcp_fn_name = name
        self.name = f"mcp__{mcp_server_id}__{name}"
        self.mcp_server_id = mcp_server_id
        self.type = "mcp_tool"

    async def invoke(self, args: dict[str,Any], env: dict[str, str] | None = None, **kwargs: Any) -> Any:
        client: McpClient = get_mcp_client_for_server(self.mcp_server_id)
        return await client.call_tool(self._mcp_fn_name, args=args)
