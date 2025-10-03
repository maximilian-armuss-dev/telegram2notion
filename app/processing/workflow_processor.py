"""
Orchestrates the entire workflow from fetching Telegram messages to saving them in Notion.

This module contains the main business logic, coordinating various services to:
1. Fetch and filter new updates from Telegram.
2. Extract content (text or transcribed audio).
3. Augment with context from existing Notion pages (RAG).
4. Process the content through an LLM to get structured actions.
5. Execute those actions on the Notion database.
6. Persist the state to avoid reprocessing.
"""
import asyncio
import logging
from typing import List, Set, Tuple, Dict, Any, Optional
from telegram import Update
from app.services.telegram_service import TelegramService
from app.services.gladia_service import GladiaService
from app.services.notion_service import NotionService
from app.services.llm_service import LLMService
from app.services.vector_service import VectorService
from app.state_manager import get_processed_update_ids, save_processed_update_ids
from app.config import settings

logger = logging.getLogger(__name__)

class WorkflowProcessor:
    """Encapsulates the logic for processing Telegram updates and saving them to Notion."""

    def __init__(self) -> None:
        """Initializes all necessary services."""
        self.telegram = TelegramService()
        self.gladia = GladiaService()
        self.notion = NotionService()
        self.llm = LLMService()
        self.vector_service = VectorService()
        # Semaphore to limit concurrent transcriptions and avoid rate-limiting.
        self.gladia_semaphore = asyncio.Semaphore(3)
        self._reset_summary()

    def _reset_summary(self) -> None:
        """Resets the summary dictionary for a new run."""
        self.summary = {
            "fetched_from_telegram": 0,
            "to_process_count": 0,
            "content_extraction_success": 0,
            "content_extraction_failed": 0,
            "processed_successfully": 0,
            "notion_actions_executed": 0,
        }

    async def run(self) -> None:
        """Public method to execute the entire workflow end-to-end."""
        logger.info("🚀 Starting workflow run...")
        self._reset_summary()
        try:
            schema = await self.notion.get_database_schema()
            processed_ids = get_processed_update_ids()
            await self._build_rag_index()
            unprocessed_updates = await self._fetch_and_filter_updates(processed_ids)
            if not unprocessed_updates:
                return
            thoughts, successful_ids = await self._extract_content_from_updates(unprocessed_updates)
            if not thoughts:
                return
            rag_context = await self._get_rag_context(thoughts)
            actions = await self.llm.process_thoughts(thoughts, schema, rag_context)
            if actions:
                await self._execute_notion_actions(actions)
            else:
                logger.warning("LLM returned no actions. The batch will be retried in the next run.")
            # Persist state only for successfully processed updates.
            processed_ids.update(successful_ids)
            save_processed_update_ids(processed_ids)
            self.summary["processed_successfully"] = len(successful_ids)
        except Exception as e:
            logger.critical(f"A critical, unhandled error occurred during the workflow run: {e}", exc_info=True)
        finally:
            self._log_summary()

    async def _build_rag_index(self) -> None:
        """Fetches all pages from Notion and builds the vector index for RAG."""
        logger.info("Building vector index from Notion pages for RAG...")
        notion_pages = await self.notion.query_all_pages()
        self.vector_service.build_index_from_notion_pages(notion_pages)
        logger.info("Vector index built successfully.")

    async def _fetch_and_filter_updates(self, processed_ids: Set[int]) -> List[Update]:
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
            # Save all fetched IDs to prevent re-fetching them next time.
            all_fetched_ids = {u.update_id for u in updates}
            save_processed_update_ids(processed_ids.union(all_fetched_ids))
        return unprocessed

    async def _extract_content_from_updates(self, updates: List[Update]) -> Tuple[List[str], List[int]]:
        """Extracts content from updates in parallel, respecting rate limits."""
        tasks = [self._process_single_update(u) for u in updates]
        extracted_results = await asyncio.gather(*tasks)
        thoughts, successful_ids = [], []
        for update_id, text in extracted_results:
            if text:
                thoughts.append(text)
                successful_ids.append(update_id)
            else:
                self.summary["content_extraction_failed"] += 1
        self.summary["content_extraction_success"] = len(thoughts)
        return thoughts, successful_ids

    async def _process_single_update(self, update: Update) -> Tuple[int, Optional[str]]:
        """Helper to extract content from a single Telegram update."""
        message = update.message
        update_id = update.update_id
        if not message:
            logger.warning(f"Update {update_id} has no 'message' content. Skipping.")
            return update_id, None
        if message.text:
            logger.info(f"Extracting text from update {update_id}.")
            return update_id, message.text
        if message.voice:
            logger.info(f"Waiting for semaphore slot to transcribe update {update_id}...")
            async with self.gladia_semaphore:
                logger.info(f"Semaphore slot acquired for update {update_id}. Starting transcription.")
                try:
                    audio_content = await self.telegram.download_voice_file(message.voice.file_id)
                    transcribed_text = await self.gladia.transcribe_audio(audio_content)
                    if transcribed_text:
                        logger.info(f"Successfully transcribed voice message from update {update_id}.")
                    return update_id, transcribed_text
                except Exception as e:
                    logger.error(f"Failed to transcribe audio for update {update_id}: {e}")
                    return update_id, None
        logger.info(f"Skipping update {update_id}: Contains no processable text or voice message.")
        return update_id, None

    async def _get_rag_context(self, thoughts: List[str]) -> str:
        """Structures thoughts, performs vector search, and returns a formatted context string."""
        logger.info("Structuring thoughts for embedding...")
        structured_thoughts = await self.llm.structure_thoughts_in_batch(thoughts)
        if not structured_thoughts:
            logger.warning("Could not structure thoughts, proceeding without RAG context.")
            return "Thought structuring failed."
        logger.info(f"Performing per-thought vector search for {len(structured_thoughts)} thoughts...")
        unique_retrieved_page_ids = set()
        all_retrieved_documents = []
        for thought_obj in structured_thoughts:
            thought_text = thought_obj.get("description", "") # Direkt das "description" Feld verwenden
            if not thought_text:
                logger.warning(f"Structured thought object has no 'description' field. Skipping RAG search for this thought: {thought_obj}")
                continue
            search_results = self.vector_service.search(thought_text, k=settings.RAG_TOP_K_PER_THOUGHT)
            if search_results:
                logger.info(f"  -> Top {len(search_results)} RAG results for thought \'{thought_text[:70]}...\':")
                for doc in search_results:
                    logger.info(f"     - Page ID: {doc.metadata.get('page_id')}, Content snippet: \'{doc.page_content[:100]}...\'")
            else:
                logger.info(f"  -> No RAG results found for thought \'{thought_text[:70]}...\'")

            for doc in search_results:
                page_id = doc.metadata.get("page_id")
                if page_id and page_id not in unique_retrieved_page_ids:
                    unique_retrieved_page_ids.add(page_id)
                    all_retrieved_documents.append(doc)
        if not all_retrieved_documents:
            return "No relevant documents found."
        return "\n\n".join(
            [f"ID: {doc.metadata['page_id']}\nContent: {doc.page_content}" for doc in all_retrieved_documents]
        )

    async def _execute_notion_actions(self, actions: List[Dict[str, Any]]) -> None:
        """Executes a list of actions (create, update, archive) on Notion in parallel, prioritizing create, then update, then archive for task queuing."""
        self.summary["notion_actions_executed"] = len(actions)
        logger.info(f"Executing {len(actions)} actions on Notion...")
        # Separate actions by type for prioritized execution
        create_actions = [a for a in actions if a.get("action") == "create"]
        update_actions = [a for a in actions if a.get("action") == "update"]
        archive_actions = [a for a in actions if a.get("action") == "archive"]
        # Concatenate into an ordered list. Tasks will still run concurrently via gather,
        # but their creation/submission order to the event loop is prioritized.
        ordered_actions = create_actions + update_actions + archive_actions
        tasks = []
        for action in ordered_actions:
            action_type = action.get("action")
            page_id = action.get("page_id")
            data = action.get("data")
            if action_type == "create" and data:
                tasks.append(self.notion.create_page(data))
            elif action_type == "update" and page_id and data:
                tasks.append(self.notion.update_page(page_id, data))
            elif action_type == "archive" and page_id:
                tasks.append(self.notion.archive_page(page_id))
            else:
                logger.warning(f"Skipping unknown or invalid action: {action}")
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Failed to execute Notion action for task {i}: {result}")

    def _log_summary(self) -> None:
        """Logs the final summary report of the workflow run."""
        to_be_retried = self.summary["to_process_count"] - self.summary["processed_successfully"]
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
          - 🔁 To be Retried:         {to_be_retried}
          
        - Notion Actions Executed:    {self.summary['notion_actions_executed']}
        -------------------------------------------------
        """
        logger.info(report)
        logger.info("Workflow run finished. ✅")

async def run_workflow() -> None:
    """Initializes and runs the WorkflowProcessor."""
    processor = WorkflowProcessor()
    await processor.run()


