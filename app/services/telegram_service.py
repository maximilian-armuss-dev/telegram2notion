import asyncio
import logging
from telegram import Bot
from telegram.ext import Application
from ..config import settings

logger = logging.getLogger(__name__)

class TelegramService:
    def __init__(self):
        self.bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        self.application = Application.builder().bot(self.bot).build()

    async def get_updates(self, offset: int = 0):
        """Fetches new messages from the Telegram Bot API using the SDK."""
        logger.info(f"Fetching Telegram updates with offset: {offset}")
        return await self.application.bot.get_updates(offset=offset, timeout=10)

    async def download_voice_file(self, file_id: str) -> bytes:
        """Downloads a voice message file using the SDK."""
        logger.info(f"Downloading voice file with ID: {file_id}")
        file = await self.bot.get_file(file_id)
        in_memory_file = await file.download_as_bytearray()
        return bytes(in_memory_file)