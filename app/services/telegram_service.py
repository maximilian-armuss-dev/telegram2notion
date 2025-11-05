"""
Service layer for interacting with the Telegram Bot API.

This module provides a simplified interface for fetching updates and downloading
voice files from Telegram, encapsulating the specifics of the python-telegram-bot SDK.
Supports both polling and webhook modes, transitioning from polling to webhook
after catching up on missed messages.
"""
import logging
from typing import List, Optional
from telegram import Bot, Update
from telegram.error import TelegramError
from app.config import settings

logger = logging.getLogger(__name__)

class TelegramService:
    """A client to interact with the Telegram Bot API using polling or webhook."""

    def __init__(self) -> None:
        """Initializes the Telegram Bot using the token from settings."""
        try:
            self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        except TelegramError as error:
            logger.critical(
                f"Failed to initialize Telegram Bot. Is the TELEGRAM_BOT_TOKEN correct? Error: {error}",
                exc_info=True,
            )
            raise

    async def get_updates(self, offset: int = 0) -> List[Update]:
        """
        Fetches new messages from the Telegram Bot API via polling.
        Args:
            offset: The identifier of the first update to be returned.
        Returns:
            A list of Update objects from the Telegram API.
        Raises:
            TelegramError: If the API call fails.
        """
        logger.info(f"Fetching Telegram updates with offset: {offset}")
        try:
            updates = await self.bot.get_updates(offset=offset, timeout=10)
            logger.info(f"Found {len(updates)} new updates from Telegram.")
            return updates
        except TelegramError as e:
            logger.error(f"Failed to fetch updates from Telegram: {e}", exc_info=True)
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

    async def set_webhook(
        self,
        url: str,
        *,
        drop_pending_updates: bool = False,
        secret_token: Optional[str] = None,
    ) -> bool:
        """
        Sets the webhook for the Telegram bot.
        Args:
            url: The public URL to set as the webhook.
            drop_pending_updates: Whether pending updates should be dropped.
            secret_token: Optional secret token to validate incoming webhooks.
        Returns:
            True if the webhook was successfully set, False otherwise.
        Raises:
            TelegramError: If the API call fails.
        """
        try:
            success = await self.bot.set_webhook(
                url=url,
                drop_pending_updates=drop_pending_updates,
                secret_token=secret_token,
            )
            if success:
                logger.info(f"Webhook successfully set to {url}")
            else:
                logger.error("Failed to set webhook.")
            return success
        except TelegramError as error:
            logger.error(f"Error setting webhook: {error}", exc_info=True)
            raise

    async def delete_webhook(self, *, drop_pending_updates: bool = False) -> bool:
        """
        Deletes the currently set webhook.
        Args:
            drop_pending_updates: Whether pending updates should be dropped.
        Returns:
            True if the webhook was successfully deleted, False otherwise.
        Raises:
            TelegramError: If the API call fails.
        """
        try:
            success = await self.bot.delete_webhook(drop_pending_updates=drop_pending_updates)
            if success:
                logger.info("Webhook successfully deleted.")
            else:
                logger.warning("Failed to delete webhook or no webhook was set.")
            return success
        except TelegramError as error:
            logger.error(f"Error deleting webhook: {error}", exc_info=True)
            raise

    async def process_webhook_update(self, update_data: dict) -> Optional[Update]:
        """
        Processes a raw update received via webhook.
        Args:
            update_data: The update data as a dictionary.
        Returns:
            The processed Update object, or None if processing failed.
        """
        try:
            update = Update.de_json(update_data, self.bot)
            if update:
                logger.info(f"Received update via webhook: {update.update_id}")
            return update
        except Exception as e:
            logger.error(f"Failed to process webhook update: {e}", exc_info=True)
            return None
