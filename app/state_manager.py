"""
Manages the persistent state of the workflow, specifically tracking processed Telegram updates.

This module handles reading from and writing to a JSON file to ensure that updates
are not processed more than once, making the workflow idempotent.
"""
import json
import logging
from pathlib import Path
from typing import Set
from app.config import settings

logger = logging.getLogger(__name__)

def _ensure_state_path() -> Path:
    """
    Ensures that the directory for the state file exists and returns the resolved path.
    Returns:
        Path: The resolved path to the state file.
    Raises:
        OSError: If the directory structure cannot be created.
    """
    state_path = Path(settings.STATE_FILE_PATH).expanduser()
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        logger.error(f"Failed to prepare state directory '{state_path.parent}': {error}", exc_info=True)
        raise
    return state_path

def get_processed_update_ids() -> Set[int]:
    """
    Reads the set of processed Telegram update_ids from the state file.
    Returns:
        A set of integers representing the IDs of already processed updates.
        Returns an empty set if the file doesn't exist or is invalid.
    """
    state_path = _ensure_state_path()
    try:
        with state_path.open('r', encoding='utf-8') as handle:
            return set(json.load(handle))
    except FileNotFoundError:
        logger.warning(
            f"State file not found at '{state_path}'. Starting with a fresh state."
        )
        return set()
    except json.JSONDecodeError:
        logger.warning(
            f"State file at '{state_path}' contains invalid JSON. Resetting processed IDs."
        )
        return set()
    except PermissionError as error:
        logger.error(
            f"Insufficient permissions to read state file '{state_path}': {error}",
            exc_info=True
        )
        return set()

def save_processed_update_ids(processed_ids: Set[int]) -> None:
    """
    Saves the given set of processed update_ids to the state file.
    Args:
        processed_ids: The set of integer IDs to save.
    """
    state_path = _ensure_state_path()
    logger.info(
        f"Saving {len(processed_ids)} processed update IDs to state file at '{state_path}'."
    )
    try:
        with state_path.open('w', encoding='utf-8') as handle:
            json.dump(sorted(list(processed_ids)), handle, indent=2)
    except PermissionError as error:
        logger.critical(
            f"Failed to save state to '{state_path}' due to insufficient permissions: {error}",
            exc_info=True
        )
        raise
    except OSError as error:
        logger.critical(
            f"Failed to persist state to '{state_path}': {error}",
            exc_info=True
        )
        raise
