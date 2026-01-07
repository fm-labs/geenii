from fastapi import APIRouter

router = APIRouter(prefix="/api/settings", tags=["settings"])

@router.get("/preferences")
def get_preferences():
    """
    Get user preferences.
    """
    # For demonstration purposes, return static preferences.
    # todo fetch from a database or user profile.
    preferences = {
        "theme": "dark",
        "notifications": True,
        "language": "en-US"
    }
    return {"preferences": preferences}

@router.post("/preferences")
def update_preferences(preferences: dict):
    """
    Update user preferences.
    """
    # todo save the preferences to a database or user profile.
    print(f"Updating preferences to: {preferences}")
    return {"status": "success", "message": "Preferences updated."}


@router.get("/integrations")
def get_enabled_integrations():
    """
    Get the list of enabled integrations.
    """
    # For demonstration purposes, return a static list.
    # todo fetch from a database or configuration.
    enabled_integrations = [
        {"name": "GitHub", "enabled": True},
        {"name": "Jira", "enabled": False},
        {"name": "Slack", "enabled": True},
    ]
    return {"integrations": enabled_integrations}


@router.post("/integrations/{name}")
def configure_integration(name: str, settings: dict):
    """
    Configure a specific integration.
    """
    # todo save the settings to a database or configuration file.
    print(f"Configuring integration '{name}' with settings: {settings}")
    return {"status": "success", "message": f"Integration '{name}' configured."}

