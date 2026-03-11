from fastapi import APIRouter
from fastapi.params import Security

from geenii.server.deps import dep_current_user
from geenii.server.routes.route_api import router as api_router
from geenii.server.routes.route_settings import router as settings_router
from geenii.server.routes.route_tools import router as tools_router
from geenii.server.routes.route_ai import router as ai_router
from geenii.server.routes.route_agents import router as agents_router
from geenii.server.routes.route_skills import router as skills_router
from geenii.server.routes.route_mcp_admin import router as mcp_router
from geenii.server.routes.route_supervisor import router as supervisor_router
from geenii.server.routes.route_scheduler import router as scheduler_router
from geenii.server.routes.route_apps import router as apps_router
from geenii.chat.chat_server_routes import router as chat_router
#from geenii.server.routes.route_ap import router as ap_router
#from geenii.server.routes.route_pubsub import router as pubsub_router
#from geenii.server.routes.route_ws import router as ws_router


app_router = APIRouter()

# API Routes
API_ROUTE_PREFIX = "/api/v1"
app_router.include_router(api_router, prefix=API_ROUTE_PREFIX)
app_router.include_router(settings_router, prefix=API_ROUTE_PREFIX, dependencies=[Security(dep_current_user)])
app_router.include_router(ai_router, prefix=API_ROUTE_PREFIX, dependencies=[Security(dep_current_user)])
app_router.include_router(tools_router, prefix=API_ROUTE_PREFIX, dependencies=[Security(dep_current_user)])
app_router.include_router(mcp_router, prefix=API_ROUTE_PREFIX, dependencies=[Security(dep_current_user)])
app_router.include_router(agents_router, prefix=API_ROUTE_PREFIX, dependencies=[Security(dep_current_user)])
app_router.include_router(skills_router, prefix=API_ROUTE_PREFIX, dependencies=[Security(dep_current_user)])
app_router.include_router(chat_router, prefix=API_ROUTE_PREFIX, dependencies=[Security(dep_current_user)])
app_router.include_router(supervisor_router, prefix=API_ROUTE_PREFIX, dependencies=[Security(dep_current_user)])
app_router.include_router(scheduler_router, prefix=API_ROUTE_PREFIX, dependencies=[Security(dep_current_user)])
app_router.include_router(apps_router, prefix=API_ROUTE_PREFIX, dependencies=[Security(dep_current_user)])
#app_router.include_router(ap_router)
#app_router.include_router(pubsub_router)
#app_router.include_router(ws_router)