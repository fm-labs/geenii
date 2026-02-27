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


def get_user_home_dir():
    home_dir = os.path.expanduser("~")
    if not home_dir:
        # fallback to HOME environment variable
        home_dir = os.environ.get("HOME", "")
    if not home_dir or not os.path.exists(home_dir):
        raise ValueError("Unable to determine user home directory.")
    return home_dir
