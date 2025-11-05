"""
FastAPI application exposing health and Telegram webhook endpoints.

This module initializes the FastAPI instance that will receive webhook callbacks
from Telegram. A callable update handler can be registered to delegate the
processing of `telegram.Update` objects to the core workflow.
"""
import asyncio
import logging
from collections import deque
from ipaddress import ip_address, ip_network
from typing import Awaitable, Callable, Deque, Dict, Optional, Set
from fastapi import FastAPI, HTTPException, Request, Response, status
from telegram import Update
from app.config import settings
from app.services.telegram_service import TelegramService

logger = logging.getLogger(__name__)

app = FastAPI()
telegram_service = TelegramService()
update_handler: Optional[Callable[[Update], Awaitable[None]]] = None
webhook_secret: Optional[str] = None
try:
    allowed_networks = tuple(ip_network(cidr) for cidr in settings.TELEGRAM_ALLOWED_CIDRS)
except ValueError as error:
    raise RuntimeError(f"Invalid CIDR supplied in TELEGRAM_ALLOWED_CIDRS: {error}") from error
_webhook_update_cache: Deque[int] = deque()
_webhook_update_cache_set: Set[int] = set()
_webhook_cache_lock = asyncio.Lock()


def register_update_handler(
    handler: Callable[[Update], Awaitable[None]],
    *,
    service: Optional[TelegramService] = None,
    secret_token: Optional[str] = None,
) -> None:
    """
    Registers the coroutine used to process Telegram updates coming from the webhook.
    Args:
        handler: Coroutine that processes a Telegram update.
        service: Optional pre-configured TelegramService instance to reuse.
        secret_token: The secret shared with Telegram for validating webhook calls.
    """
    global update_handler, telegram_service, webhook_secret
    update_handler = handler
    if service is not None:
        telegram_service = service
    if secret_token is None:
        raise ValueError("A webhook secret token must be provided when registering the update handler.")
    webhook_secret = secret_token


@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check() -> Dict[str, str]:
    """
    Returns a simple status payload for health monitoring.
    Returns:
        A dictionary containing the health status.
    """
    return {"status": "ok"}


@app.post("/telegram/webhook", status_code=status.HTTP_200_OK)
async def telegram_webhook(request: Request) -> Response:
    """
    Receives webhook updates from Telegram and hands them to the registered handler.
    Args:
        request: The incoming FastAPI request containing the Telegram payload.
    Returns:
        A minimal HTTP 200 response confirming receipt.
    Raises:
        HTTPException: If validation fails for headers, payload, or source IP.
    """
    if update_handler is None:
        logger.error("Webhook received but no update handler is registered.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Update handler not ready.",
        )
    if webhook_secret is None:
        logger.error("Webhook secret is not initialized.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret unavailable.",
        )
    secret_token = request.headers.get("x-telegram-bot-api-secret-token")
    if not secret_token:
        logger.warning("Webhook rejected: Missing X-Telegram-Bot-Api-Secret-Token header.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Missing secret token.",
        )
    if secret_token != webhook_secret:
        logger.warning("Webhook rejected: Invalid secret token provided.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid secret token.",
        )
    client_ip = _extract_client_ip(request)
    if not client_ip:
        logger.warning("Webhook rejected: Unable to determine client IP.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unable to determine client IP.",
        )
    if not _is_ip_allowed(client_ip):
        logger.warning(f"Webhook rejected: Client IP {client_ip} not in allowed Telegram ranges.")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden source IP.",
        )
    content_type = request.headers.get("content-type", "").lower()
    if "application/json" not in content_type:
        logger.warning(f"Webhook rejected due to unsupported content type: {content_type}")
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Content-Type must be application/json.",
        )
    try:
        payload = await request.json()
    except Exception as error:
        logger.error(f"Failed to parse webhook payload: {error}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload.",
        ) from error
    update = await telegram_service.process_webhook_update(payload)
    if update is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to deserialize Telegram update.",
        )
    if not await _mark_update_if_new(update.update_id):
        logger.info(f"Skipping duplicate webhook update {update.update_id}.")
        return Response(status_code=status.HTTP_200_OK)
    asyncio.create_task(_dispatch_update(update))
    return Response(status_code=status.HTTP_200_OK)


async def _dispatch_update(update: Update) -> None:
    """
    Queues the processing of a Telegram update to avoid blocking the webhook response.
    Args:
        update: The Telegram update to process.
    """
    if update_handler is None:
        logger.error("Update handler missing while dispatching queued update.")
        return
    try:
        await update_handler(update)
    except Exception as error:
        logger.error(f"Error while processing update {update.update_id} in background: {error}", exc_info=True)


def _extract_client_ip(request: Request) -> Optional[str]:
    """
    Extracts the originating IP address from Cloudflare or proxy headers.
    Args:
        request: Incoming FastAPI request.
    Returns:
        The IP address as a string, or None if it cannot be determined.
    """
    for header in ("cf-connecting-ip", "x-real-ip"):
        value = request.headers.get(header)
        if value:
            return value.strip()
    if request.client and request.client.host:
        return request.client.host
    return None


def _is_ip_allowed(ip_str: str) -> bool:
    """
    Checks whether the provided IP address belongs to the allowed Telegram ranges.
    Args:
        ip_str: IP address as string.
    Returns:
        True if the IP is within an allowed range, otherwise False.
    """
    try:
        client_ip = ip_address(ip_str)
    except ValueError:
        logger.warning(f"Invalid IP address string received: {ip_str}")
        return False
    return any(client_ip in network for network in allowed_networks)


async def _mark_update_if_new(update_id: int) -> bool:
    """
    Records the update ID if it was not processed recently.
    Args:
        update_id: Telegram update identifier.
    Returns:
        True if the update was new and recorded, otherwise False.
    """
    async with _webhook_cache_lock:
        if update_id in _webhook_update_cache_set:
            return False
        cache_size = settings.WEBHOOK_UPDATE_CACHE_SIZE
        if len(_webhook_update_cache) >= cache_size:
            oldest = _webhook_update_cache.popleft()
            _webhook_update_cache_set.discard(oldest)
        _webhook_update_cache.append(update_id)
        _webhook_update_cache_set.add(update_id)
        return True
