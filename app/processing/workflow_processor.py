import asyncio
import logging
from app.services.telegram_service import TelegramService
from app.services.gladia_service import GladiaService
from app.services.notion_service import NotionService
from app.services.llm_service import LLMService

logger = logging.getLogger(__name__)
STATE_FILE = "last_update_id.txt"

def get_last_update_id() -> int:
    """Reads the last processed update_id from a file."""
    try:
        with open(STATE_FILE, 'r') as f:
            return int(f.read().strip())
    except (FileNotFoundError, ValueError):
        return 0

def save_last_update_id(update_id: int):
    """Saves the latest processed update_id to a file."""
    with open(STATE_FILE, 'w') as f:
        f.write(str(update_id))

async def _process_single_update(update, telegram: TelegramService, gladia: GladiaService) -> str | None:
    """Processes a single Telegram update and returns the text content if available."""
    message = update.message
    if not message:
        return None
    if message.text:
        logger.info(f"Processing text message: '{message.text[:30]}...'")
        return message.text
    elif message.voice:
        logger.info(f"Processing voice message from chat ID {message.chat_id}.")
        try:
            audio_content = await telegram.download_voice_file(message.voice.file_id)
            return await gladia.transcribe_audio(audio_content)
        except Exception as e:
            logger.error(f"Could not transcribe audio for update {update.update_id}: {e}")
            return None
    return None

async def run_workflow():
    """Main function to orchestrate the entire workflow."""
    logger.info("🚀 Starting workflow run...")

    telegram = TelegramService()
    gladia = GladiaService()
    notion = NotionService()
    llm = LLMService(prompt_template_path="prompts/gemini_prompt.md")

    last_update_id = get_last_update_id()
    updates = await telegram.get_updates(offset=last_update_id + 1)
    if not updates:
        logger.info("No new messages found. ✨")
        return
    logger.info(f"Found {len(updates)} new updates.")
    latest_update_id = last_update_id
    
    tasks = []
    for update in updates:
        latest_update_id = max(latest_update_id, update.update_id)
        tasks.append(_process_single_update(update, telegram, gladia))
        
    all_thoughts_results = await asyncio.gather(*tasks)
    all_thoughts = [thought for thought in all_thoughts_results if thought] # Filter out None values
    if not all_thoughts:
        logger.warning("No processable content (text/voice) in new messages.")
        save_last_update_id(latest_update_id)
        return

    logger.info(f"Collected {len(all_thoughts)} thoughts. Processing with LLM...")

    try:
        schema = await notion.get_database_schema()
        actions = await llm.process_thoughts(all_thoughts, schema)
        
        logger.info(f"LLM returned {len(actions)} actions. Executing on Notion...")
        for action in actions:
            if action.get("action") == "create":
                await notion.create_page(action.get("data"))
            elif action.get("action") == "update" and "page_id" in action:
                await notion.update_page(action["page_id"], action.get("data"))
            else:
                logger.warning(f"Skipping action '{action.get('action')}', page_id in action = {'page_id' in action}")

    except Exception as e:
        logger.critical(f"A critical error occurred during LLM or Notion processing: {e}", exc_info=True)
    finally:
        save_last_update_id(latest_update_id)
        logger.info("Workflow run finished. ✅")