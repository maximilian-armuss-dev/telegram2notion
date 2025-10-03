"""
Manages the persistent state of the workflow, specifically tracking processed Telegram updates.

This module handles reading from and writing to a JSON file to ensure that updates
are not processed more than once, making the workflow idempotent.
"""
import json
import logging
from typing import Set
from app.config import settings

logger = logging.getLogger(__name__)

def get_processed_update_ids() -> Set[int]:
    """
    Reads the set of processed Telegram update_ids from the state file.
    Returns:
        A set of integers representing the IDs of already processed updates.
        Returns an empty set if the file doesn't exist or is invalid.
    """
    try:
        with open(settings.STATE_FILE_PATH, 'r', encoding='utf-8') as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning(
            f"State file not found or invalid at '{settings.STATE_FILE_PATH}'. Starting with a fresh state."
        )
        return set()

def save_processed_update_ids(processed_ids: Set[int]) -> None:
    """
    Saves the given set of processed update_ids to the state file.
    Args:
        processed_ids: The set of integer IDs to save.
    """
    logger.info(
        f"Saving {len(processed_ids)} processed update IDs to state file at '{settings.STATE_FILE_PATH}'."
    )
    try:
        with open(settings.STATE_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(sorted(list(processed_ids)), f, indent=2)
    except IOError as e:
        logger.critical(
            f"Failed to save state to '{settings.STATE_FILE_PATH}': {e}",
            exc_info=True
        )
        raise
