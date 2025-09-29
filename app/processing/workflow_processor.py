import asyncio
import logging
import json
from app.services.telegram_service import TelegramService
from app.services.gladia_service import GladiaService
from app.services.notion_service import NotionService
from app.services.llm_service import LLMService

# --- CONFIGURATION & STATE (Module Level) ---

logger = logging.getLogger(__name__)
STATE_FILE = "processed_update_ids.json"

def get_processed_update_ids() -> set[int]:
    """Reads the set of processed update_ids from a file for efficient lookups."""
    try:
        with open(STATE_FILE, 'r') as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_processed_update_ids(processed_ids: set[int]):
    """Saves the set of processed update_ids to a file."""
    with open(STATE_FILE, 'w') as f:
        json.dump(sorted(list(processed_ids)), f)

# --- WORKFLOW PROCESSOR CLASS ---

class WorkflowProcessor:
    """Encapsulates the entire logic for processing Telegram updates and saving them to Notion."""

    def __init__(self):
        """Initializes all necessary services."""
        self.telegram = TelegramService()
        self.gladia = GladiaService()
        self.notion = NotionService()
        self.llm = LLMService(prompt_template_path="prompts/gemini_prompt.md")
        self.gladia_semaphore = asyncio.Semaphore(3)
        self._reset_summary()

    def _reset_summary(self):
        """Resets the summary dictionary for a new run."""
        self.summary = {
            "fetched_from_telegram": 0, "to_process_count": 0, "content_extraction_success": 0,
            "content_extraction_failed": 0, "processed_successfully": 0, "notion_actions_executed": 0,
        }

    async def _fetch_and_filter_updates(self, processed_ids: set[int]) -> list:
        """Fetches new updates from Telegram and filters out already processed ones."""
        last_known_id = max(processed_ids) if processed_ids else 0
        updates = await self.telegram.get_updates(offset=last_known_id + 1)
        self.summary["fetched_from_telegram"] = len(updates)
        
        if not updates:
            logger.info("No new messages found. ✨")
            return []

        unprocessed = [u for u in updates if u.update_id not in processed_ids]
        self.summary["to_process_count"] = len(unprocessed)

        if not unprocessed:
            logger.info("All fetched updates were already processed.")
            all_fetched_ids = {u.update_id for u in updates}
            save_processed_update_ids(processed_ids.union(all_fetched_ids))
        
        return unprocessed

    async def _extract_content(self, updates: list) -> tuple[list[str], list[int]]:
        """Extracts content from updates in parallel, respecting rate limits."""
        tasks = [
            _process_single_update_content(u, self.telegram, self.gladia, self.gladia_semaphore)
            for u in updates
        ]
        extracted_results = await asyncio.gather(*tasks)

        thoughts = []
        successful_ids = []
        for update_id, text in extracted_results:
            if text:
                thoughts.append(text)
                successful_ids.append(update_id)
            else:
                self.summary["content_extraction_failed"] += 1
        
        self.summary["content_extraction_success"] = len(thoughts)
        return thoughts, successful_ids

    async def _process_batch(self, thoughts: list[str], schema: dict):
        """Processes a batch of thoughts with the LLM and executes actions on Notion."""
        logger.info(f"Sending a batch of {len(thoughts)} thoughts to the LLM...")
        actions = await self.llm.process_thoughts(thoughts, schema)
        self.summary["notion_actions_executed"] = len(actions) if actions else 0

        if not actions:
            logger.warning("LLM returned no actions for the batch. The batch will be retried.")
            return

        logger.info(f"LLM returned {self.summary['notion_actions_executed']} actions. Executing on Notion...")
        notion_tasks = []
        for action in actions:
            action_type = action.get("action")
            if action_type == "create":
                notion_tasks.append(self.notion.create_page(action.get("data")))
            elif action_type == "update" and action.get("page_id"):
                notion_tasks.append(self.notion.update_page(action["page_id"], action.get("data")))
            elif action_type == "archive" and action.get("page_id"):
                notion_tasks.append(self.notion.archive_page(action["page_id"]))
            else:
                logger.warning(f"Skipping unknown or invalid action: {action}")
        
        if notion_tasks:
            await asyncio.gather(*notion_tasks)

    def _log_summary(self):
        """Logs the final summary report of the workflow run."""
        retried_next_run = self.summary["to_process_count"] - self.summary["processed_successfully"]
        report = f"""
        \n-------------------------------------------------
        📊 WORKFLOW RUN SUMMARY
        -------------------------------------------------
        - Telegram Updates Fetched:   {self.summary['fetched_from_telegram']}
        - Updates to Process:         {self.summary['to_process_count']} (new or failed)
        
        - Content Extraction:
          - ✅ Success:               {self.summary['content_extraction_success']}
          - ❌ Failed:                {self.summary['content_extraction_failed']}
          
        - Final Processing:
          - ✅ Processed & Saved:     {self.summary['processed_successfully']}
          - 🔁 To be Retried:         {retried_next_run}
          
        - Notion Actions Executed:    {self.summary['notion_actions_executed']}
        -------------------------------------------------
        """
        logger.info(report)
        logger.info("Workflow run finished. ✅")

    async def run(self):
        """Public method to execute the entire workflow."""
        logger.info("🚀 Starting workflow run...")
        self._reset_summary()
        
        try:
            schema = await self.notion.get_database_schema()
            processed_ids = get_processed_update_ids()

            unprocessed_updates = await self._fetch_and_filter_updates(processed_ids)
            if not unprocessed_updates:
                return

            thoughts, successful_ids = await self._extract_content(unprocessed_updates)
            if not thoughts:
                return

            await self._process_batch(thoughts, schema)
            
            # Persist successful state
            processed_ids.update(successful_ids)
            save_processed_update_ids(processed_ids)
            self.summary["processed_successfully"] = len(successful_ids)

        except Exception as e:
            logger.critical(f"A critical, unhandled error occurred during the workflow run: {e}", exc_info=True)
        finally:
            self._log_summary()

# --- HELPER & ENTRYPOINT (Module Level) ---

async def _process_single_update_content(update, telegram, gladia, semaphore) -> tuple[int, str | None]:
    """Standalone helper to extract content. Stays outside the class as it doesn't need class state."""
    message = update.message; update_id = update.update_id
    if not message: logger.warning(f"Update {update_id} has no 'message' content. Skipping."); return update_id, None
    if message.text: logger.info(f"Extracting text from update {update_id}."); return update_id, message.text
    elif message.voice:
        logger.info(f"Waiting for semaphore slot to transcribe update {update_id}...")
        async with semaphore:
            logger.info(f"Semaphore slot acquired for update {update_id}. Starting transcription.")
            try:
                audio_content = await telegram.download_voice_file(message.voice.file_id)
                transcribed_text = await gladia.transcribe_audio(audio_content)
                logger.info(f"Successfully transcribed voice message from update {update_id}.")
                return update_id, transcribed_text
            except Exception as e:
                logger.error(f"Failed to transcribe audio for update {update_id}: {e}")
                return update_id, None
    else: logger.info(f"Skipping update {update_id}: Contains no processable text or voice message."); return update_id, None

# This is the main entrypoint function called by `main.py`
async def run_workflow():
    """Initializes and runs the WorkflowProcessor."""
    processor = WorkflowProcessor()
    await processor.run()