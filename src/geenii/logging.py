import logging
from logging.handlers import RotatingFileHandler

from geenii.config import DATA_DIR

LOG_FORMAT1 = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
LOG_FORMAT2 = "%(asctime)s - %(levelname)s - %(message)s"

formatter = logging.Formatter(LOG_FORMAT1)

def get_file_log_handler(name):
    file_handler = logging.FileHandler(f"{DATA_DIR}/logs/{name}.log")
    file_handler.setFormatter(formatter)
    return file_handler

def get_console_log_handler():
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    return console_handler

def get_rotating_file_log_handler(name):
    rotating_file_handler = RotatingFileHandler(
        f"{DATA_DIR}/logs/{name}.log",
        maxBytes=10_000_000,   # 10 MB
        backupCount=10         # keep 10 old files
    )
    rotating_file_handler.setFormatter(formatter)
    return rotating_file_handler