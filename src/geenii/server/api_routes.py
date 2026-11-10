from fastapi import APIRouter

from geenii.g import get_app_info

router = APIRouter(prefix="", tags=["api"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/info")
async def info() -> dict:
    info = get_app_info()
    return info
