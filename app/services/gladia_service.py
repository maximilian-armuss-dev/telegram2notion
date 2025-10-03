"""
Service layer for interacting with the Gladia AI Speech-to-Text API.

This module handles the transcription of audio files by uploading them to the
Gladia API, starting the transcription process, and polling for the result.
"""
import asyncio
import logging
import httpx
from typing import Optional
from app.config import settings

logger = logging.getLogger(__name__)

class GladiaService:
    """A client for the Gladia AI transcription service."""

    def __init__(self) -> None:
        """Initializes the service with configuration from settings."""
        self.base_url = settings.GLADIA_API_URL
        self.headers = {"x-gladia-key": settings.GLADIA_API_KEY}
        self.polling_interval = settings.GLADIA_POLLING_INTERVAL_SECONDS

    async def transcribe_audio(self, audio_content: bytes, filename: str = "voice.oga") -> Optional[str]:
        """
        Transcribes audio content using the Gladia AI API.
        This method orchestrates the three main steps:
        1. Upload the audio file.
        2. Start the transcription job.
        3. Poll for the final result.
        Args:
            audio_content: The raw audio data as bytes.
            filename: The name of the file to be sent to the API.
        Returns:
            The full transcribed text as a string, or None if transcription fails.
        """
        # The client is created per-request to ensure thread-safety in async environments.
        async with httpx.AsyncClient(timeout=120) as client:
            try:
                audio_url = await self._upload_file(client, audio_content, filename)
                logger.info(f"Gladia: Audio uploaded to {audio_url}")
                result_url = await self._start_transcription(client, audio_url)
                logger.info(f"Gladia: Transcription started. Polling {result_url}")
                transcript = await self._poll_for_result(client, result_url)
                logger.info("Gladia: Transcription successful.")
                return transcript
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Gladia HTTP error: {e.response.status_code} - {e.response.text}",
                    exc_info=True
                )
            except Exception as e:
                logger.error(
                    f"An unexpected error occurred during transcription: {e}", exc_info=True
                )
        return None

    async def _upload_file(self, client: httpx.AsyncClient, content: bytes, filename: str) -> str:
        """Uploads the audio file and returns the URL for transcription."""
        files = {'audio': (filename, content, 'audio/ogg')}
        response = await client.post(
            f"{self.base_url}/upload",
            headers=self.headers,
            files=files
        )
        response.raise_for_status()
        return response.json()["audio_url"]

    async def _start_transcription(self, client: httpx.AsyncClient, audio_url: str) -> str:
        """Starts the transcription job and returns the URL to poll for results."""
        payload = {"audio_url": audio_url, "detect_language": True}
        response = await client.post(
            f"{self.base_url}/pre-recorded",
            headers=self.headers,
            json=payload
        )
        response.raise_for_status()
        return response.json()["result_url"]

    async def _poll_for_result(self, client: httpx.AsyncClient, result_url: str) -> str:
        """Polls the result URL until the transcription is complete or fails."""
        while True:
            await asyncio.sleep(self.polling_interval)
            response = await client.get(result_url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            status = data.get("status")
            if status == "done":
                return data["result"]["transcription"]["full_transcript"]
            if status == "error":
                error_message = data.get('error_message', 'Unknown transcription error.')
                logger.error(f"Gladia transcription failed: {error_message}")
                raise Exception(f"Gladia transcription failed: {error_message}")
            logger.info(f"Gladia transcription status: {status or 'unknown'}. Retrying...")
