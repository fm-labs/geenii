from typing import Annotated, Any

from fastapi import APIRouter, Body, HTTPException, Path

from geenii import config

router = APIRouter(prefix="/settings", tags=["settings"])

# Key of the UI user settings in settings.json: {"userSettings": {"<namespace>": {...}}}
USER_SETTINGS_KEY = "userSettings"

Namespace = Annotated[str, Path(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")]


def _user_settings(settings: dict) -> dict:
    section = settings.get(USER_SETTINGS_KEY)
    return section if isinstance(section, dict) else {}


@router.get("/user")
def get_user_settings() -> dict[str, dict]:
    """All namespaces of the user settings (namespaces that aren't objects are left out)."""
    section = _user_settings(config.read_user_settings())
    return {ns: values for ns, values in section.items() if isinstance(values, dict)}


@router.get("/user/{namespace}")
def get_user_settings_namespace(namespace: Namespace) -> dict[str, Any]:
    """The user settings of NAMESPACE; empty if none are saved yet."""
    values = _user_settings(config.read_user_settings()).get(namespace)
    return values if isinstance(values, dict) else {}


@router.put("/user/{namespace}")
def put_user_settings_namespace(namespace: Namespace, values: Annotated[dict[str, Any], Body()]) -> dict[str, Any]:
    """Replace the user settings of NAMESPACE with VALUES; returns the saved values."""

    def update(settings: dict) -> None:
        section = settings.get(USER_SETTINGS_KEY)
        if not isinstance(section, dict):
            section = settings[USER_SETTINGS_KEY] = {}
        section[namespace] = values

    try:
        config.update_user_settings(update)
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Can't update the user settings: {e}")
    return values
