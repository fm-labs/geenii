import logging
import re

import pydantic
from fastapi import APIRouter, HTTPException, Response

from geenii.datamodels import MCPToolCallRequest
from geenii.mcp_config import get_mcp_config, get_mcp_config_for_server, get_mcp_client_for_server, \
    read_root_mcp_config, save_mcp_server_config, delete_mcp_server_config, get_root_mcp_config_path

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["mcp"])


def _server_summary(name: str, cfg: dict) -> dict:
    """Public view of a server config. Env values are masked, as they commonly hold secrets."""
    _type = cfg.get("type") or ("stdio" if cfg.get("command") else "http" if cfg.get("url") else None)
    return {
        "name": name,
        "type": _type,
        "url": cfg.get("url"),
        "command": cfg.get("command"),
        "args": cfg.get("args", []),
        "env": {key: "********" for key in (cfg.get("env") or {})},
    }


MASKED_VALUE = "********"
SERVER_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")
# keys holding secrets: values are masked when read and kept when sent back masked
SECRET_KEYS = ("env", "headers")


class McpServerCreateRequest(pydantic.BaseModel):
    name: str
    config: dict


def _mask_config(cfg: dict) -> dict:
    masked = dict(cfg)
    for loc in SECRET_KEYS:
        if isinstance(cfg.get(loc), dict):
            masked[loc] = {key: MASKED_VALUE for key in cfg[loc]}
    return masked


def _unmask_config(cfg: dict, stored: dict | None) -> dict:
    """Replace masked values with the stored ones. A masked value without a stored one is rejected."""
    cfg = dict(cfg)
    for loc in SECRET_KEYS:
        values = cfg.get(loc)
        if not isinstance(values, dict):
            continue
        stored_values = (stored or {}).get(loc) or {}
        unmasked = {}
        for key, value in values.items():
            if value == MASKED_VALUE:
                if key not in stored_values:
                    raise HTTPException(status_code=400, detail=f"No stored value for masked {loc} entry '{key}'.")
                value = stored_values[key]
            unmasked[key] = value
        cfg[loc] = unmasked
    return cfg


def _validate_server_config(cfg: dict) -> None:
    if not cfg.get("command") and not cfg.get("url"):
        raise HTTPException(status_code=400, detail="A server config needs either a 'command' or a 'url'.")
    if "args" in cfg and not (isinstance(cfg["args"], list) and all(isinstance(a, str) for a in cfg["args"])):
        raise HTTPException(status_code=400, detail="'args' must be a list of strings.")
    for loc in SECRET_KEYS:
        if loc in cfg and not (isinstance(cfg[loc], dict) and all(isinstance(v, str) for v in cfg[loc].values())):
            raise HTTPException(status_code=400, detail=f"'{loc}' must be an object of strings.")


def _get_root_server_config(server_name: str) -> dict:
    """The server's entry in the root mcp.json, which is the only file the API writes."""
    cfg = read_root_mcp_config()["mcpServers"].get(server_name)
    if cfg is None:
        if get_mcp_config_for_server(server_name) is not None:
            raise HTTPException(status_code=409, detail=f"MCP server '{server_name}' is not defined in "
                                                        f"{get_root_mcp_config_path()}, so it can't be changed here.")
        raise HTTPException(status_code=404, detail=f"MCP server '{server_name}' not found.")
    return cfg


def _get_server_config(server_name: str) -> dict:
    cfg = get_mcp_config_for_server(server_name)
    if cfg is None:
        raise HTTPException(status_code=404, detail=f"MCP server '{server_name}' not found.")
    return cfg


@router.get("/servers")
def list_servers(reload: bool = False) -> list[dict]:
    servers = get_mcp_config(reload=reload).get("mcpServers", {})
    return [_server_summary(name, cfg) for name, cfg in servers.items()]


@router.post("/servers", status_code=201)
def create_server(request: McpServerCreateRequest) -> dict:
    if not SERVER_NAME_PATTERN.match(request.name):
        raise HTTPException(status_code=400, detail="Server names may only contain letters, digits, - and _.")
    if get_mcp_config_for_server(request.name) is not None:
        raise HTTPException(status_code=409, detail=f"MCP server '{request.name}' already exists.")
    cfg = _unmask_config(request.config, None)
    _validate_server_config(cfg)
    save_mcp_server_config(request.name, cfg)
    return _server_summary(request.name, cfg)


@router.get("/servers/{server_name}/config")
def get_server_config(server_name: str) -> dict:
    """The server's full mcp.json entry, with secret values masked."""
    return _mask_config(_get_server_config(server_name))


@router.put("/servers/{server_name}")
def update_server(server_name: str, config: dict) -> dict:
    stored = _get_root_server_config(server_name)
    cfg = _unmask_config(config, stored)
    _validate_server_config(cfg)
    save_mcp_server_config(server_name, cfg)
    return _server_summary(server_name, cfg)


@router.delete("/servers/{server_name}", status_code=204)
def delete_server(server_name: str) -> Response:
    _get_root_server_config(server_name)
    delete_mcp_server_config(server_name)
    return Response(status_code=204)


@router.get("/servers/{server_name}")
def get_server(server_name: str) -> dict:
    # sync endpoint: connecting to the MCP server blocks, so FastAPI runs it in its threadpool
    cfg = _get_server_config(server_name)
    client = get_mcp_client_for_server(server_name)
    try:
        info = client.info()
    except Exception as e:
        logger.error(f"Error fetching info from MCP server '{server_name}': {e}")
        raise HTTPException(status_code=502, detail=f"Failed to connect to MCP server '{server_name}': {e}")
    return {**_server_summary(server_name, cfg), **info}


@router.post("/servers/{server_name}/tool/call")
def call_server_tool(server_name: str, request: MCPToolCallRequest):
    _get_server_config(server_name)
    client = get_mcp_client_for_server(server_name)
    try:
        result = client.call_tool(request.tool_name, request.arguments or {})
    except Exception as e:
        logger.error(f"Error calling tool '{request.tool_name}' on MCP server '{server_name}': {e}")
        raise HTTPException(status_code=502, detail=f"Tool call failed: {e}")
    return result.model_dump() if hasattr(result, "model_dump") else result
