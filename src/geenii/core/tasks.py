import logging

logger = logging.getLogger(__name__)


def cleanup(*args):
    """Perform maintenance tasks"""
    logger.info("Performing cleanup tasks...")


def run_agent(params: list[str], env: dict | None = None) -> None:
    """Run the main loop for the agent"""
    logger.info(f"run_agent {params} env={env}")
