from typing import List

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["api"])


@router.get("/health")
async def health():
    return {"status": "ok"}


@router.get("/info")
async def info() -> dict:
    return dict({
        "version": "0.1.0",
    })

