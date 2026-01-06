import dataclasses
from typing import List

from fastapi import APIRouter, HTTPException
from fastmcp import Client
from fastmcp.client.client import CallToolResult
from fastmcp.client.tasks import ToolTask
from mcp.types import Prompt

from geenii.datamodels import MCPServerConfig, MCPToolCallRequest, MCPServerInfo, MCPToolCallResponse
from geenii.mcp.client import get_mcp_config, read_mcp_config_json, write_mcp_config_json, \
    get_mcp_client_for_server, get_mcp_config_for_server

router = APIRouter(prefix="/api/mcp", tags=["mcp"])



### MCP
@router.get("/servers", response_model=List[MCPServerConfig])
async def get_mcp_servers() -> List[MCPServerConfig]:
    """
    List all available MCP servers.
    """
    config = get_mcp_config()
    print("get_mcp_servers config:", config)
    if "mcpServers" not in config:
        return []
    return [MCPServerConfig(**server) for server in config["mcpServers"]]

# @router.get("/servers/{server_name}")
# async def mcp_server_details(server_name: str):
#     """
#     Get details of a specific MCP server.
#     """
#     config = get_mcp_config()
#     if "mcpServers" not in config or server_name not in config["mcpServers"]:
#         return {"error": f"MCP server '{server_name}' not found."}
#
#     server_details = config["mcpServers"][server_name]
#     return {"server_name": server_name, "details": server_details}

@router.post("/servers")
async def add_mcp_server(request: MCPServerConfig) -> MCPServerConfig:
    """
    Add a new MCP server configuration.
    """
    try:
        server_name = request.name
        config = get_mcp_config()
        if "mcpServers" not in config:
            config["mcpServers"] = {}

        if get_mcp_config_for_server(server_name) is not None:
           raise ValueError(f"MCP server '{server_name}' already exists.")

        # Validate the request
        if not request.url and not request.command:
            raise ValueError("Either 'url' or 'command' must be provided to configure the MCP server.")

        # Add the new server configuration
        server_config_dict = {
            "name": server_name,
            "url": request.url,
            "command": request.command,
            "args": request.args or []
        }
        server_config = MCPServerConfig(**server_config_dict)
        config["mcpServers"].append(server_config_dict)

        # Save the updated configuration
        write_mcp_config_json(config)
        # Reload the MCP client configuration
        get_mcp_config(reload=True)

        return server_config
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/servers/{server_name}")
async def get_mcp_server_info(server_name: str) -> MCPServerInfo:
    """
    Connect to a specific MCP server.
    """
    config = read_mcp_config_json()
    server_config = get_mcp_config_for_server(server_name=server_name)
    if not server_config:
        raise HTTPException(status_code=404, detail="Server not found.")

    if "url" not in server_config and ("command" not in server_config or "args" not in server_config):
        raise HTTPException(status_code=400, detail="Either 'url' or 'command' must be provided.")

    # Create a client that connects to the specified server
    #_config = {"mcpServers": {server_name: server_config}}
    #client = Client(_config)
    client = get_mcp_client_for_server(server_name=server_name)

    async with client:
        try:
            #initialize_result = await client.initialize_result
            tools = await client.list_tools()
            resources = await client.list_resources()
            prompts: list[Prompt] = await client.list_prompts()

            info_dict = {
                "name": server_name,
                "status": "connected",
                #"message": f"Connected to MCP server '{server_name}' successfully.",
                #"initialize_result": initialize_result.model_dump(),
                "tools": [tool.model_dump() for tool in tools],
                "resources": [res.model_dump() for res in resources],
                "prompts": [prompt.model_dump() for prompt in prompts],
            }
            print(info_dict)
            return MCPServerInfo(**info_dict)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

@router.delete("/servers/{server_name}")
def delete_mcp_server(server_name: str) -> MCPServerConfig:
    """
    Delete an MCP server configuration.
    """
    try:
        config = get_mcp_config()
        if "mcpServers" not in config:
            raise ValueError("No MCP servers configured.")

        server_configs = config["mcpServers"]
        server_to_delete = get_mcp_config_for_server(server_name=server_name)
        if not server_to_delete:
            raise ValueError(f"MCP server '{server_name}' not found.")

        # filter out the server to delete
        updated_server_configs = [s for s in server_configs if s["name"] != server_name]
        config["mcpServers"] = updated_server_configs

        # Save the updated configuration
        write_mcp_config_json(config)
        # Reload the MCP client configuration
        get_mcp_config(reload=True)

        return MCPServerConfig(**server_to_delete)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/servers/{server_name}/tool/call")
async def call_mcp_server_tool(server_name: str, request: MCPToolCallRequest) -> MCPToolCallResponse:
    """
    Call a specific MCP tool with the given arguments.
    """
    tool_name = request.tool_name
    arguments = request.arguments
    try:
        client = get_mcp_client_for_server(server_name=server_name)
    except Exception as e:
        return MCPToolCallResponse(**{"tool_name": tool_name, "arguments": arguments, "error": str(e)})

    async with client:
        try:
            print("Calling MCP tool:", tool_name, "with arguments):", arguments)
            result: CallToolResult = await client.call_tool(tool_name, arguments=arguments)
            return MCPToolCallResponse(**{"tool_name": tool_name, "arguments": arguments, "result": dataclasses.asdict(result)})
        except Exception as e:
            return MCPToolCallResponse(**{"tool_name": tool_name, "arguments": arguments, "error": str(e)})


# @router.get("/tools")
# async def mcp_tools():
#     """List all available MCP tools from the configured servers."""
#     try:
#         client = get_mcp_client()
#     except Exception as e:
#         return {"error": str(e)}
#
#     async with client:
#         tools = await client.list_tools()
#         return tools