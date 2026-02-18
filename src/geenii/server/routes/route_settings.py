import os
import json

from fastapi import APIRouter

router = APIRouter(prefix="/api/settings", tags=["settings"])


def get_user_dir():
    home_dir = os.path.expanduser("~")
    user_dir = os.path.join(home_dir, ".geenii")
    if not os.path.exists(user_dir):
        os.makedirs(user_dir, exist_ok=True)
    return user_dir


def read_user_settings():
    user_settings_path = os.path.join(get_user_dir(), "settings.json")
    default_settings = {
        "theme": "dark",
        "notifications": True,
        "language": "en-US"
    }
    if os.path.exists(user_settings_path):
        try:
            with open(user_settings_path, "r") as f:
                settings = json.load(f)
                return settings
        except Exception as e:
            print(f"Error reading user settings: {e}")
            return default_settings
    else:
        return default_settings


def write_user_settings(settings: dict):
    print(f"Saving settings: {settings}")
    user_settings_path = os.path.join(get_user_dir(), "settings.json")
    try:
        with open(user_settings_path, "w") as f:
            json.dump(settings, f, indent=4)
    except Exception as e:
        print(f"Error writing user settings: {e}")


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
