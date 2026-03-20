from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.params import Depends
from starlette.requests import Request
from starlette.responses import FileResponse

from geenii.apps import AppRegistry
from geenii.config import DATA_DIR

APPS_BASE_DIR = Path(f"{DATA_DIR}/apps")

router = APIRouter(prefix="/apps", tags=["apps"])

def dep_app_registry(req: Request):
    return req.app.state.app_registry


@router.get("/")
def list_apps(apps: AppRegistry = Depends(dep_app_registry)):
    """List all available apps."""
    return {"apps": apps.list_apps()}


# @router.get("{app_id}/files/{file_path:path}")
# async def serve_user_file(app_id: str, file_path: str):
#     if not app_id.isalnum():
#         raise HTTPException(status_code=400, detail="Invalid app ID")
#
#     # check if app_id is valid (e.g. matches a known app or follows a certain pattern)
#     if app_id not in [app["name"] for app in APPS]:
#         raise HTTPException(status_code=404, detail="App not found")
#
#     app_base_dir = Path(APPS_BASE_DIR / "apps" / app_id)
#     if not app_base_dir.is_dir() or not app_base_dir.resolve().relative_to(APPS_BASE_DIR.resolve()):
#         raise HTTPException(status_code=404, detail="App dir not found")
#
#     full_path = app_base_dir / app_id / file_path
#
#     # sanitize against path traversal!
#     # :critical
#     try:
#         full_path.resolve().relative_to(app_base_dir.resolve())
#     except ValueError:
#         # todo log this as a potential attack attempt
#         raise HTTPException(status_code=400, detail="Invalid path")
#
#     if not full_path.is_file():
#         raise HTTPException(status_code=404, detail="File not found")
#     # :critical-end
#     return FileResponse(full_path)