import json
import logging
from langchain_google_genai import ChatGoogleGenerativeAI
from datetime import date
from ..config import settings

logger = logging.getLogger(__name__)

class LLMService:
    def __init__(self, prompt_template_path: str):
        """Initializes the LLM service with the Gemini model and a prompt template."""
        self.model = ChatGoogleGenerativeAI(model="gemini-pro", google_api_key=settings.GOOGLE_API_KEY)
        try:
            with open(prompt_template_path, 'r', encoding='utf-8') as f:
                self.prompt_template = f.read()
        except FileNotFoundError:
            logger.critical(f"Prompt template file not found at: {prompt_template_path}")
            raise

    def _build_prompt(self, thoughts_text: str, schema_json: str) -> str:
        """Builds the final prompt by injecting context into the template."""
        prompt = self.prompt_template.replace('[[SCHEMA PLACEHOLDER]]', schema_json)
        prompt = prompt.replace('[[TEXT PLACEHOLDER]]', thoughts_text)
        prompt = prompt.replace('{{ $today }}', str(date.today()))
        return prompt

    async def process_thoughts(self, thoughts: list[str], notion_schema: dict) -> list[dict]:
        """Processes a list of thoughts with the LLM and returns structured actions for Notion."""
        if not thoughts:
            return []

        concatenated_thoughts = ""
        for i, thought in enumerate(thoughts, 1):
            concatenated_thoughts += f"USER MESSAGE {i}:\n\n{thought}\n\n"

        schema_as_string = json.dumps(notion_schema, indent=2)

        final_prompt = self._build_prompt(concatenated_thoughts, schema_as_string)

        logger.info("Sending request to Gemini LLM...")
        response = await self.model.ainvoke(final_prompt)
        content = response.content
        if content.strip().startswith("```json"):
            content = content.strip()[7:-3]
        logger.info("Received and parsed response from Gemini.")

        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON from LLM response: {e}")
            logger.debug(f"Raw LLM response content: {content}")
            return []