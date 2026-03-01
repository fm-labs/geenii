import logging

from rich.logging import RichHandler

from geenii.cli.gcli import gcli

logging.basicConfig(
    level="INFO",
    format="%(message)s",
    handlers=[
        RichHandler(
            show_time=True,  # show timestamps
            omit_repeated_times=False,  # show timestamp every line
            show_level=True,
            show_path=True,  # hide file path
            rich_tracebacks=False,  # beautiful exception tracebacks
        )
    ]
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    gcli()
