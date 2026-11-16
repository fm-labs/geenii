import logging
import os
import re
from logging.handlers import RotatingFileHandler

from rich.logging import RichHandler

from geenii.config import GEENII_CACHE_DIR

LOG_FORMAT1 = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_FORMAT2 = "%(asctime)s - %(levelname)s - %(message)s"
LOG_FORMAT3 = "%(asctime)s - %(levelname)s - %(message)s"

formatter = logging.Formatter(LOG_FORMAT1)


DEFAULT_LOG_NAME = "geenii"


def resolve_log_name(log_name: str | None = None) -> str:
    """Name of the rotating log file (without .log): GEENII_LOG_NAME wins over log_name."""
    name = os.getenv("GEENII_LOG_NAME") or log_name or DEFAULT_LOG_NAME
    # The name becomes a file name in the logs dir; keep it to a plain basename
    return re.sub(r"[^A-Za-z0-9_.-]", "-", name).lstrip(".") or DEFAULT_LOG_NAME


def init_logging(log_name: str | None = None, force: bool = False):
    """Configure root logging (GEENII_LOGGING=rich|plain, default plain).

    :param log_name: Rotating log file name for plain logging (``<cache>/logs/<name>.log``).
                     The GEENII_LOG_NAME environment variable overrides it.
    :param force: Replace existing root handlers. Without it, this is a no-op when
                  logging was already configured (logging.basicConfig semantics).
    """
    if os.getenv("GEENII_LOGGING", "plain") == "rich":
        logging.basicConfig(
            force=force,
            level="INFO",
            # format="%(message)s",
            format="%(name)s: %(message)s",
            handlers=[
                RichHandler(
                    show_time=True,  # show timestamps
                    omit_repeated_times=False,  # show timestamp every line
                    show_level=True,
                    show_path=True,  # hide file path
                    rich_tracebacks=False,  # beautiful exception tracebacks
                )
            ],
        )
    else:
        logging.basicConfig(
            force=force,
            level=logging.INFO,
            format=LOG_FORMAT1,
            handlers=[
                get_console_log_handler(),
                get_rotating_file_log_handler(resolve_log_name(log_name)),
            ],
        )
    # logging.getLogger("httpx").setLevel(logging.WARNING)


def get_console_log_handler():
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    return console_handler


def get_file_log_handler(name):
    os.makedirs(f"{GEENII_CACHE_DIR}/logs", exist_ok=True)
    file_handler = logging.FileHandler(f"{GEENII_CACHE_DIR}/logs/{name}.log")
    file_handler.setFormatter(formatter)
    return file_handler


def get_rotating_file_log_handler(name):
    os.makedirs(f"{GEENII_CACHE_DIR}/logs", exist_ok=True)
    rotating_file_handler = RotatingFileHandler(
        f"{GEENII_CACHE_DIR}/logs/{name}.log",
        maxBytes=10_000_000,  # 10 MB
        backupCount=10,  # keep 10 old files
    )
    rotating_file_handler.setFormatter(formatter)
    return rotating_file_handler
