import asyncio
import logging
from fastapi import FastAPI, HTTPException
from .processing.workflow_processor import run_workflow
from .logging_config import setup_logging

setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Thought Processor",
    description="An agent to process thoughts from Telegram and organize them in Notion.",
    version="1.0.0"
)

@app.post("/run-workflow", summary="Trigger the Telegram to Notion workflow")
async def trigger_workflow():
    """
    Manually triggers the workflow to fetch messages from Telegram,
    process them, and update Notion.
    """
    try:
        await run_workflow()
        return {"status": "success", "message": "Workflow executed successfully."}
    except Exception as e:
        logger.error(f"Workflow execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    logger.info("Running workflow directly from script...")
    asyncio.run(run_workflow())