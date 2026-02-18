import os
from typing import List

from fastapi import APIRouter

from geenii.config import APP_VERSION
from geenii.server.routes.route_settings import get_user_dir

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/info")
async def info() -> dict:
    return dict({
        "version": APP_VERSION,
        "cwd": os.getcwd(),
        "home_dir": os.path.expanduser("~"),
        "user_dir": get_user_dir()
    })
