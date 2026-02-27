import os


def get_os_name() -> str:
    platform = os.environ.get("PLATFORM", "").lower()
    if platform in ("windows", "linux", "darwin"):
        return platform
    # Fallback to sys.platform if PLATFORM env var is not set or unrecognized
    import sys
    if sys.platform.startswith("win"):
        return "windows"
    elif sys.platform.startswith("linux"):
        return "linux"
    elif sys.platform.startswith("darwin"):
        return "darwin"
    else:
        return "unknown"


def get_user_home() -> str:
    if get_os_name() == "windows":
        return os.environ.get("USERPROFILE", "")
    else:
        return os.environ.get("HOME", "")
