from fastapi import APIRouter, Depends
from starlette.requests import Request

from geenii.tool.registry import ToolRegistry

router = APIRouter(prefix="/tools", tags=["tools"])


def dep_tool_registry(request: Request):
    return request.app.state.tool_registry

@router.get("/")
def get_tools(registry: ToolRegistry = Depends(dep_tool_registry)):
    definitions = registry.list_definitions()
    print(f"Found {len(definitions)} tools in registry.")
    return definitions

@router.post("/{tool_name}/execute")
async def execute_tool(tool_name: str, args: dict, registry: ToolRegistry = Depends(dep_tool_registry)):
    tool = registry.get(tool_name)
    if not tool:
        raise ValueError(f"Tool '{tool_name}' not found.")
    return await tool.invoke(args=args)