import os

from fastapi import APIRouter
from pydantic import BaseModel

from geenii import config

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectInfo(BaseModel):
    path: str
    trusted: bool
    exists: bool


@router.get("/")
def list_projects() -> list[ProjectInfo]:
    """The projects configured in the user settings, with their resolved paths."""
    return [
        ProjectInfo(path=path, trusted=conf.get("trusted") is True, exists=os.path.isdir(path))
        for path, conf in config.get_projects().items()
    ]
