import logging

from geenii.cli.geenii import geecli
from geenii.g import init_app_directories
from geenii.logs import init_logging

init_logging()
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    init_app_directories()
    geecli()
