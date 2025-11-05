"""
Service layer for interacting with the Language Model (LLM).

This module encapsulates the logic for:
1.  Structuring raw text thoughts into a machine-readable format using an LLM.
2.  Processing structured thoughts against a Notion schema to generate actionable
    commands (create, update, archive).
It leverages LangChain for building and executing the LLM chains.
"""
import json
import logging
import pytz
import re
from datetime import datetime
from typing import List, Dict, Any
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import settings
from app.models import ActionList

logger = logging.getLogger(__name__)

class LLMService:
    """A client to process text and generate Notion actions using an LLM."""

    def __init__(self) -> None:
        """Initializes the LLM, parsers, and prompt templates from configuration."""
        self.model = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0.4,  # Higher temperature for more creative/flexible JSON generation
        )
        self.parser = PydanticOutputParser(pydantic_object=ActionList)
        self.main_prompt_template = self._load_prompt_template(
            file_path=settings.PROMPT_GEMINI_MAIN_PATH,
            input_variables=["schema", "today", "thoughts", "retrieved_documents"],
        )
        self.structuring_prompt_template = self._load_prompt_template(
            file_path=settings.PROMPT_THOUGHT_STRUCTURING_PATH,
            input_variables=["thoughts"],
        )

    def _load_prompt_template(
        self, file_path: str, input_variables: List[str]
    ) -> PromptTemplate:
        """Loads a prompt template from a file and handles errors."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                template_string = f.read()
            return PromptTemplate(
                template=template_string,
                input_variables=input_variables
            )
        except FileNotFoundError:
            logger.critical(f"Prompt template file not found at: {file_path}")
            raise

    @staticmethod
    def _clean_llm_json_response(response_content: str) -> str:
        """
        Cleans the raw LLM string output to make it valid JSON.
        Removes markdown code fences (```json ... ```) and leading/trailing whitespace.
        """
        cleaned = response_content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```[a-zA-Z]*\s*", "", cleaned, count=1)
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()

    async def structure_thoughts_in_batch(self, thoughts: List[str]) -> List[Dict[str, Any]]:
        """
        Processes a batch of raw thought strings and structures them into a list of dictionaries.
        Args:
            thoughts: A list of strings, where each string is a raw thought.
        Returns:
            A list of dictionaries, each representing a structured thought, or an empty list on failure.
        """
        if not thoughts:
            return []
        concatenated_thoughts = "\n".join(thoughts)
        chain = self.structuring_prompt_template | self.model
        logger.info(f"Structuring a batch of {len(thoughts)} thoughts...")
        try:
            logger.debug(
                "--- PROMPT SENT TO STRUCTURING LLM ---\n%s\n---------------------------------",
                self.structuring_prompt_template.format(thoughts=concatenated_thoughts),
            )
            response = await chain.ainvoke({"thoughts": concatenated_thoughts})
            logger.debug(
                "--- RAW STRUCTURING LLM RESPONSE ---\n%s\n------------------------",
                response.content,
            )
            cleaned_response = self._clean_llm_json_response(response.content)
            structured_thoughts = json.loads(cleaned_response)
            if isinstance(structured_thoughts, list):
                logger.info(f"Successfully structured {len(structured_thoughts)} thoughts.")
                return structured_thoughts
            logger.error(f"Structuring LLM did not return a list. Response: {structured_thoughts}")
            return []
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from structuring LLM response: {response.content}", exc_info=True)
            return []
        except Exception as e:
            logger.error(f"An unexpected error occurred while structuring thoughts: {e}", exc_info=True)
            return []

    async def process_thoughts(
        self, thoughts: List[str], notion_schema: Dict[str, Any], retrieved_documents: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Processes thoughts to generate a list of Notion actions using the main LLM chain.
        Args:
            thoughts: A list of raw thought strings.
            notion_schema: The simplified schema of the target Notion database.
            retrieved_documents: Context string from RAG search to be included in the prompt.
        Returns:
            A list of dictionaries, where each dictionary is a valid Notion action.
        """
        if not thoughts:
            return []
        concatenated_thoughts = "\n\n---\n\n".join(thoughts)
        schema_as_string = json.dumps(notion_schema, indent=2)
        timezone = pytz.timezone(settings.TIMEZONE)
        current_date = datetime.now(timezone).strftime("%Y-%m-%d")
        chain = self.main_prompt_template | self.model
        prompt_input = {
            "schema": schema_as_string,
            "today": current_date,
            "thoughts": concatenated_thoughts,
            "retrieved_documents": retrieved_documents,
        }
        logger.info(f"Sending a batch of {len(thoughts)} thoughts to the main LLM...")
        logger.debug(
            "--- FINAL PROMPT SENT TO LLM ---\n%s\n---------------------------------",
            self.main_prompt_template.format(**prompt_input),
        )
        try:
            response = await chain.ainvoke(prompt_input)
            logger.debug(
                "--- RAW LLM RESPONSE ---\n%s\n------------------------",
                response.content,
            )
            cleaned_response = self._clean_llm_json_response(response.content)
            parsed_response = self.parser.parse(cleaned_response)
            actions_list = parsed_response.root
            logger.info(f"LLM returned {len(actions_list)} validated actions.")
            # Convert Pydantic models back to dictionaries for the Notion service.
            return [action.model_dump(exclude_none=True) for action in actions_list]
        except Exception as e:
            logger.error(f"Failed to invoke LLM or parse/validate response: {e}", exc_info=True)
            return []
