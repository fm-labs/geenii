from typing import List

from fastapi import APIRouter

from geenii.settings import APP_VERSION

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/info")
async def info() -> dict:
    return dict({
        "version": APP_VERSION,
    })

