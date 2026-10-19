import os
from pathlib import Path

import subprocess
import logging

from geenii import config
from geenii.tool.common import ToolCallContext
from geenii.tool.registry import ToolRegistry

logger = logging.getLogger(__name__)


def is_file_in_allowed_dirs(file_path: str | Path, wd: str | None = None) -> bool:
    dirs = [wd, config.GEENII_WORKING_DIR]

    user_settings = config.read_user_settings()
    if "allowed_dirs" in user_settings and isinstance(
        user_settings["allowed_dirs"], list
    ):
        allowed_dirs = user_settings["allowed_dirs"]
        dirs.extend(allowed_dirs)

    for _dir in dirs:
        if _dir is not None and is_file_in_allowed_dir(file_path, wd=_dir):
            return True
    return False


def is_file_in_allowed_dir(file_path: str | Path, wd: str) -> bool:
    """Return True if file_path resolves to a location inside the working dir."""
    try:
        logger.debug(f"check is_file_in_working_dir file_path={file_path} wd={wd}")
        wd = Path(wd).resolve(strict=False)
        target = Path(file_path).resolve(strict=False)
    except (OSError, ValueError):
        # null bytes, embedded NULs, unresolvable paths, symlink loops
        return False
    return target != wd and wd in target.parents


def init_core_tools(tool_registry: ToolRegistry) -> None:

    # tool_registry = ToolRegistry()

    # @tool_registry.tool()
    # def file_exists(file_path: str) -> bool:
    #     """
    #     Check if a file exists at the specified path.
    #
    #     :param file_path: The path to the file to check.
    #     :return: True if the file exists, False otherwise.
    #     """
    #     return os.path.isfile(file_path)

    def _normalize_path(path: str, base_dir: str) -> str:
        if not Path(path).is_absolute():
            path = Path(base_dir) / path
        return str(path.resolve(strict=False).absolute())

    @tool_registry.tool(name="read")
    def file_read(file_path: str, *, ctx: ToolCallContext) -> str:
        """
        Read and return the contents of a file.

        :param file_path: The path to the file to read.
        :return: The contents of the file as a string.
        """
        wd = ctx.cwd or os.getcwd()
        file_path = _normalize_path(file_path, wd)
        if not is_file_in_allowed_dirs(file_path, wd):
            logger.critical(
                f"SECURITY ALERT! Attempting to read file from {file_path}. wd={wd}"
            )
            return "You are not allowed to read this file."

        logger.warning(f"file_read: {file_path}")
        with open(file_path, "r") as f:
            return f.read()

    @tool_registry.tool(name="write")
    def file_write(file_path: str, contents: str, *, ctx: ToolCallContext) -> str:
        """
        Write the contents to a file.

        :param file_path: The path to the file to write to.
        :param contents: The contents to write to the file.
        """
        wd = ctx.cwd or os.getcwd()
        file_path = _normalize_path(file_path, wd)
        if not is_file_in_allowed_dirs(file_path, wd):
            logger.critical(
                f"SECURITY ALERT! Attempting to write to {file_path}. wd={wd}"
            )
            return "You are not allowed to write this file."

        logger.warning(f"file_write: {file_path}")
        with open(file_path, "w") as f:
            f.write(contents)

        return f"Contents successfully written to {file_path}"


    @tool_registry.tool()
    def display_desktop_notification(
        message: str, title: str = "Message from Geenii"
    ) -> str:
        """
        Show a desktop notification with the given title and message.

        :param message: The message body of the notification.
        :param title: The title of the notification.
        :return: A message indicating that the notification has been sent.
        """

        def _escape_applescript(s: str) -> str:
            return (
                s.replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\n", "\\n")
                .replace("\r", "\\r")
                .replace("\t", "\\t")
            )

        script = (
            f'display dialog "{_escape_applescript(message)}"'
            f' with title "{_escape_applescript(title)}"'
            f' buttons {{"OK"}} giving up after 60'
        )
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True
        )
        if result.returncode != 0:
            return f"Failed to send notification: {result.stderr.strip()}"
        return f"Notification sent: {title} - {message}"


    # @tool_registry.tool()
    # def get_weather_forecast(location: str) -> str:
    #     """
    #     Get the current weather forecast for a specified location.
    #
    #     :param location: The location to get the weather forecast for.
    #     :return: A string containing the weather forecast information.
    #     """
    #     # Placeholder implementation - replace with actual API call to a weather service
    #     return f"The current weather in {location} is sunny with a high of 25°C and a low of 15°C."
