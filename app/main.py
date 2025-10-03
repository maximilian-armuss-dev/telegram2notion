"""
Main entrypoint for the Telegram-to-Notion workflow application.

This script initializes the logging configuration and starts the main asynchronous
workflow processor. It is intended to be run as a standalone script or as the
target for a scheduler (e.g., a cron job).
"""
import asyncio
import logging
from app.logging_config import setup_logging
from app.processing.workflow_processor import run_workflow

setup_logging()
logger = logging.getLogger(__name__)

def main() -> None:
    """Synchronous wrapper to run the main async workflow."""
    logger.info("Application starting...")
    try:
        asyncio.run(run_workflow())
    except Exception as e:
        logger.critical(f"Application terminated with a critical error: {e}", exc_info=True)
    finally:
        logger.info("Application finished.")

if __name__ == "__main__":
    main()
