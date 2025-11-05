"""
Bootstrapper for the hybrid polling and webhook runtime.

This module ensures the application catches up on pending Telegram updates via polling,
configures the webhook, and finally delegates to FastAPI (served by uvicorn) to receive
new updates in real time.
"""
import asyncio
import logging
import uvicorn
from app.config import settings
from app.processing.workflow_processor import WorkflowProcessor
from app.services.telegram_service import TelegramService
from app.webhook_api import app as fastapi_app, register_update_handler

logger = logging.getLogger(__name__)

async def _run_uvicorn_server() -> None:
    """
    Starts the uvicorn server hosting the FastAPI webhook application.
    Raises:
        RuntimeError: If the server exits unexpectedly before serving.
    """
    config = uvicorn.Config(
        fastapi_app,
        host=settings.WEBHOOK_HOST,
        port=settings.WEBHOOK_PORT,
        log_level=settings.LOG_LEVEL.lower(),
    )
    server = uvicorn.Server(config)
    logger.info(f"Starting FastAPI webhook server via uvicorn on {settings.WEBHOOK_HOST}:{settings.WEBHOOK_PORT}.")
    await server.serve()

async def _prepare_webhook_mode(
    telegram_service: TelegramService,
    processor: WorkflowProcessor,
    secret_token: str,
) -> None:
    """
    Performs the polling catch-up and configures the Telegram webhook.
    Args:
        telegram_service: Shared Telegram service instance.
        processor: Workflow processor that handles updates.
    Raises:
        RuntimeError: If setting the webhook fails.
    """
    logger.info("Disabling webhook (if any) before polling catch-up.")
    await telegram_service.delete_webhook(drop_pending_updates=False)
    await _run_startup_polling(processor)
    logger.info(f"Configuring webhook with target URL {settings.WEBHOOK_URL}.")
    success = await telegram_service.set_webhook(
        settings.WEBHOOK_URL,
        drop_pending_updates=False,
        secret_token=secret_token,
    )
    if not success:
        raise RuntimeError("Failed to set webhook with Telegram.")
    logger.info(f"Webhook mode ready at {settings.WEBHOOK_URL}")

async def _run_startup_polling(processor: WorkflowProcessor) -> None:
    """
    Executes the short-lived polling phase to process backlog updates before enabling the webhook.
    Args:
        processor: The workflow processor responsible for handling updates.
    """
    max_runs = settings.STARTUP_POLLING_MAX_RUNS
    if max_runs <= 0:
        logger.info("Startup polling disabled by configuration.")
        return
    logger.info(f"Running startup polling catch-up with up to {max_runs} pass(es).")
    for current_pass in range(1, max_runs + 1):
        logger.info(f"Starting startup polling pass {current_pass}.")
        has_pending_updates = await processor.run()
        if not has_pending_updates:
            logger.info(f"Startup polling completed after {current_pass} pass(es); backlog drained.")
            return
    logger.warning(
        f"Startup polling reached the maximum of {max_runs} pass(es); pending updates may remain for webhook processing."
    )

async def start_hybrid_runtime() -> None:
    """
    Entry point that wires services, catches up messages, and starts the webhook server.
    Raises:
        RuntimeError: Propagates critical failures during startup.
    """
    telegram_service = TelegramService()
    processor = WorkflowProcessor(telegram_service=telegram_service)
    configured_secret = settings.WEBHOOK_SECRET_TOKEN
    if not configured_secret:
        raise RuntimeError("WEBHOOK_SECRET_TOKEN must be set to enable webhook mode.")
    secret_token = configured_secret
    min_length = settings.WEBHOOK_SECRET_LENGTH
    if len(secret_token) < min_length:
        raise RuntimeError(
            f"WEBHOOK_SECRET_TOKEN must be at least {min_length} characters long to satisfy configuration."
        )
    logger.info("Using webhook secret token from settings.")
    settings.WEBHOOK_SECRET_TOKEN = secret_token
    register_update_handler(
        processor.process_update,
        service=telegram_service,
        secret_token=secret_token,
    )
    if settings.WEBHOOK_ENABLED:
        await _prepare_webhook_mode(telegram_service, processor, secret_token)
        await _run_uvicorn_server()
        return
    logger.warning("Webhook mode disabled. Running single polling pass only.")
    await processor.run()

def run() -> None:
    """Runs the hybrid runtime inside a new asyncio event loop."""
    try:
        asyncio.run(start_hybrid_runtime())
    except KeyboardInterrupt:
        logger.info("Shutdown requested by user.")
