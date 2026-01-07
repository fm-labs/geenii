from fastapi import APIRouter

from geenii.server.routes.route_api import router as api_router
from geenii.server.routes.route_settings import router as settings_router
from geenii.server.routes.route_tools import router as tools_router
from geenii.server.routes.route_ai import router as ai_router
from geenii.server.routes.route_ap import router as ap_router
from geenii.server.routes.route_assistants import router as assistants_router
from geenii.server.routes.route_mcp_admin import router as mcp_router
from geenii.server.routes.route_pubsub import router as pubsub_router
from geenii.server.routes.route_ws import router as ws_router


app_router = APIRouter()
app_router.include_router(api_router)
app_router.include_router(settings_router)
app_router.include_router(tools_router)
app_router.include_router(mcp_router)
app_router.include_router(ai_router)
app_router.include_router(assistants_router)
app_router.include_router(ap_router)
app_router.include_router(pubsub_router)
app_router.include_router(ws_router)