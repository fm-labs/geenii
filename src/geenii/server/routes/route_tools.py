from docutils.writers.latex2e import definitions
from fastapi import APIRouter, Depends
from starlette.requests import Request

from geenii.tools import ToolRegistry

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])


def dep_tool_registry(request: Request):
    return request.app.state.tool_registry

@router.get("/")
def get_tools(registry: ToolRegistry = Depends(dep_tool_registry)):
    definitions = registry.list_definitions()
    print(f"Found {len(definitions)} tools in registry.")
    return definitions

# @router.post("/{tool_name}/execute")
# def execute_tool(tool_name: str, args: dict, registry: ToolRegistry = Depends(dep_tool_registry)):
#     tool = registry.get(tool_name)
#     if not tool:
#         raise ValueError(f"Tool '{tool_name}' not found.")
#     return tool.invoke(**args)