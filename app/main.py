"""
Main entrypoint for the Telegram-to-Notion workflow application.

This script initializes the logging configuration and starts the hybrid runtime
that first catches up via polling and then serves the webhook through FastAPI.
"""
import logging
from app.logging_config import setup_logging
from app.bootstrap import run as run_bootstrap

setup_logging()
logger = logging.getLogger(__name__)

def main() -> None:
    """Starts the hybrid polling + webhook runtime."""
    logger.info("Application starting...")
    try:
        run_bootstrap()
    except Exception as error:
        logger.critical(f"Application terminated with a critical error: {error}", exc_info=True)
    finally:
        logger.info("Application finished.")

if __name__ == "__main__":
    main()
