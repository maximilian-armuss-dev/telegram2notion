"""
Service layer for interacting with the Telegram Bot API.

This module provides a simplified interface for fetching updates and downloading
voice files from Telegram, encapsulating the specifics of the python-telegram-bot SDK.
"""
import logging
from typing import List
from telegram import Bot, Update
from telegram.error import TelegramError
from telegram.ext import Application
from app.config import settings

logger = logging.getLogger(__name__)

class TelegramService:
    """A client to interact with the Telegram Bot API."""

    def __init__(self) -> None:
        """Initializes the Telegram Bot and Application using the token from settings."""
        try:
            self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
            self.application = Application.builder().bot(self.bot).build()
        except Exception as e:
            logger.critical(f"Failed to initialize Telegram Bot. Is the TELEGRAM_BOT_TOKEN correct? Error: {e}")
            raise

    async def get_updates(self, offset: int = 0) -> List[Update]:
        """
        Fetches new messages from the Telegram Bot API.
        Args:
            offset: The identifier of the first update to be returned.
        Returns:
            A list of Update objects from the Telegram API.
        Raises:
            TelegramError: If the API call fails.
        """
        logger.info(f"Fetching Telegram updates with offset: {offset}")
        try:
            updates = await self.application.bot.get_updates(offset=offset, timeout=10)
            logger.info(f"Found {len(updates)} new updates from Telegram.")
            return updates
        except TelegramError as e:
            logger.error(f"Failed to fetch updates from Telegram: {e}", exc_info=True)
            # Re-raising allows the caller to handle the failed API call.
            raise

    async def download_voice_file(self, file_id: str) -> bytes:
        """
        Downloads a voice message file by its file_id.
        Args:
            file_id: The unique identifier for the voice file on Telegram's servers.
        Returns:
            The raw audio content as a bytes object.
        Raises:
            TelegramError: If the file download fails.
        """
        logger.info(f"Downloading voice file with ID: {file_id}")
        try:
            file = await self.bot.get_file(file_id)
            in_memory_file = await file.download_as_bytearray()
            logger.info(f"Successfully downloaded voice file {file_id}.")
            return bytes(in_memory_file)
        except TelegramError as e:
            logger.error(f"Failed to download voice file {file_id}: {e}", exc_info=True)
            raise
