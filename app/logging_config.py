"""
Module for configuring the application's logging system.

This module provides a centralized function to set up the root logger, ensuring
consistent logging behavior across the application, especially in containerized
environments like Docker.
"""
import logging
import sys

def setup_logging() -> None:
    """
    Configures the root logger for the application.
    Sets up basic logging to standard output with a predefined format,
    which is suitable for Docker environments.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s", # This is a logging format string, not a Python string format. It should remain as is.
        stream=sys.stdout,  # Log to standard output, which Docker captures
    )
