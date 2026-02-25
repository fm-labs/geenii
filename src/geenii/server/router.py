from fastapi import APIRouter

from geenii.server.routes.route_api import router as api_router
from geenii.server.routes.route_settings import router as settings_router
from geenii.server.routes.route_tools import router as tools_router
from geenii.server.routes.route_ai import router as ai_router
#from geenii.server.routes.route_ap import router as ap_router
from geenii.server.routes.route_assistants import router as assistants_router
from geenii.server.routes.route_wizards import router as wizards_router
from geenii.server.routes.route_mcp_admin import router as mcp_router
#from geenii.server.routes.route_pubsub import router as pubsub_router
#from geenii.server.routes.route_ws import router as ws_router
from geenii.chat.chat_server_routes import router as chat_router
from geenii.server.routes.route_supervisor import router as supervisor_router
from geenii.server.routes.route_apps import router as apps_router


app_router = APIRouter()
app_router.include_router(api_router)
app_router.include_router(settings_router)
app_router.include_router(ai_router)
app_router.include_router(tools_router)
app_router.include_router(mcp_router)
#app_router.include_router(assistants_router)
app_router.include_router(wizards_router)
app_router.include_router(chat_router)
app_router.include_router(supervisor_router)
app_router.include_router(apps_router)
#app_router.include_router(ap_router)
#app_router.include_router(pubsub_router)
#app_router.include_router(ws_router)