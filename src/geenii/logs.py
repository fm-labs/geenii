import os
import logging
from logging.handlers import RotatingFileHandler

from rich.logging import RichHandler

from geenii.config import CACHE_DIR

LOG_FORMAT1 = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_FORMAT2 = "%(asctime)s - %(levelname)s - %(message)s"
LOG_FORMAT3 = "%(asctime)s - %(levelname)s - %(message)s"

formatter = logging.Formatter(LOG_FORMAT1)


def init_logging():
    if os.getenv("GEENII_LOGGING", "rich") == "rich":
        logging.basicConfig(
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
            level=logging.INFO,
            format=LOG_FORMAT1,
            handlers=[
                get_console_log_handler(),
                get_rotating_file_log_handler("geenii"),
            ],
        )
    #logging.getLogger("httpx").setLevel(logging.WARNING)


def get_console_log_handler():
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    return console_handler


def get_file_log_handler(name):
    os.makedirs(f"{CACHE_DIR}/logs", exist_ok=True)
    file_handler = logging.FileHandler(f"{CACHE_DIR}/logs/{name}.log")
    file_handler.setFormatter(formatter)
    return file_handler


def get_rotating_file_log_handler(name):
    os.makedirs(f"{CACHE_DIR}/logs", exist_ok=True)
    rotating_file_handler = RotatingFileHandler(
        f"{CACHE_DIR}/logs/{name}.log",
        maxBytes=10_000_000,  # 10 MB
        backupCount=10,  # keep 10 old files
    )
    rotating_file_handler.setFormatter(formatter)
    return rotating_file_handler
