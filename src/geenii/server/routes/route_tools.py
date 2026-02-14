from fastapi import APIRouter

from geenii.g import get_tool_registry

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])

@router.get("/")
def get_tools():
    tool_registry = get_tool_registry()
    tools = tool_registry.list_definitions()
    return tools