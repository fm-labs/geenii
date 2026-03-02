import os
import json

from fastapi import APIRouter

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/")
def get_settings():
    """
    Get user settings.
    """
    # For demonstration purposes, return static settings.
    # todo fetch from a database or user profile.
    settings = read_user_settings()
    return {"settings": settings}

@router.post("/")
def update_settings(settings: dict):
    """
    Update user settings.
    """
    existing_user_settings = read_user_settings()
    new_user_settings = settings.copy()
    new_user_settings.update(existing_user_settings)
    write_user_settings(new_user_settings)
    return {"status": "success", "message": "Preferences updated."}


@router.get("/integrations")
def list_integrations():
    """
    Get the list of available integrations.
    """
    # todo implement me
    integrations = []
    return {"integrations": integrations}


@router.post("/integrations/{name}")
def configure_integration(name: str, settings: dict):
    """
    Configure a specific integration.
    """
    # todo save the settings to a database or configuration file.
    print(f"Configuring integration '{name}' with settings: {settings}")
    return {"status": "success", "message": f"Integration '{name}' configured."}
