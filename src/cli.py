import logging

from geenii.cli.geenii import geecli
from geenii.logs import init_logging

init_logging()
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    geecli()
