import os
from typing import List

from fastapi import APIRouter

from geenii.config import APP_VERSION
from geenii.server.routes.route_settings import get_user_data_dir, get_user_home_dir
from geenii.utils.system_util import get_system_report

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/info")
async def info() -> dict:
    data = dict({
        "app": {
            "version": APP_VERSION,
            "cwd": os.getcwd(),
            "home_dir": get_user_home_dir(),
            "user_dir": get_user_data_dir()
        }
    })
    data.update(get_system_report())

    # if not in DEV_MODE, remove the env variables from the report for security reasons
    ALLOWED_ENV_VARS = ["PATH", "HOME", "USER", "USERNAME"]
    if not os.environ.get("DEV_MODE", "0") == "1":
        if "env" in data:
            data["env"] = {k: v for k, v in data["env"].items() if k in ALLOWED_ENV_VARS}
    return data

