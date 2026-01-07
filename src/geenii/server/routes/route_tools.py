from fastapi import APIRouter

router = APIRouter(prefix="/ai/v1/tools", tags=["tools"])


@router.get("/")
def get_tools():
    # For demonstration purposes, return a static list of tools.
    # In a real implementation, this could fetch from a database or configuration.
    tools = [
        {"name": "Calculator", "description": "Performs basic arithmetic operations."},
        {"name": "Web Search", "description": "Searches the web for information."},
        {"name": "Weather", "description": "Provides current weather information."},
    ]
    return tools