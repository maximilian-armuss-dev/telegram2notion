import httpx
import asyncio
import logging
from ..config import settings

logger = logging.getLogger(__name__)

class GladiaService:
    def __init__(self):
        self.base_url = "https://api.gladia.io/v2"
        self.headers = {"x-gladia-key": settings.GLADIA_API_KEY}

    async def transcribe_audio(self, audio_content: bytes, filename: str = "voice.oga") -> str:
        """Transcribes audio content using the Gladia AI API."""
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
                logger.error(f"Gladia HTTP error: {e.response.status_code} - {e.response.text}")
                raise
            except Exception as e:
                logger.error(f"An unexpected error occurred during transcription: {e}")
                raise

    async def _upload_file(self, client: httpx.AsyncClient, content: bytes, filename: str) -> str:
        files = {'audio': (filename, content, 'audio/ogg')}
        response = await client.post(f"{self.base_url}/upload", headers=self.headers, files=files)
        response.raise_for_status()
        return response.json()["audio_url"]

    async def _start_transcription(self, client: httpx.AsyncClient, audio_url: str) -> str:
        payload = {"audio_url": audio_url, "detect_language": True}
        response = await client.post(f"{self.base_url}/pre-recorded", headers=self.headers, json=payload)
        response.raise_for_status()
        return response.json()["result_url"]

    async def _poll_for_result(self, client: httpx.AsyncClient, result_url: str) -> str:
        while True:
            await asyncio.sleep(5)
            response = await client.get(result_url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            if data.get("status") == "done":
                return data["result"]["transcription"]["full_transcript"]
            elif data.get("status") == "error":
                raise Exception(f"Gladia transcription failed: {data.get('error_message')}")
            logger.info(f"Gladia transcription status: {data.get('status', 'unknown')}. Retrying...")