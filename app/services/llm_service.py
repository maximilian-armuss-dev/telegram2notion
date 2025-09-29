import json
import logging
import pytz
from datetime import datetime
from typing import List, Literal, Optional

from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field, RootModel

from app.config import settings

logger = logging.getLogger(__name__)

# --- Pydantic Models for Notion's Data Structure ---

class NotionContent(BaseModel):
    content: str

class TextPart(BaseModel):
    text: NotionContent

class TitleProperty(BaseModel):
    title: List[TextPart]

class RichTextProperty(BaseModel):
    rich_text: List[TextPart]

class SelectOption(BaseModel):
    name: str

class SelectProperty(BaseModel):
    select: SelectOption

class StatusProperty(BaseModel):
    status: SelectOption

class DateContent(BaseModel):
    start: str

class DateProperty(BaseModel):
    date: DateContent

class MultiSelectProperty(BaseModel):
    multi_select: List[SelectOption]

class ActionData(BaseModel):
    Name: Optional[TitleProperty] = None
    description: Optional[RichTextProperty] = None
    progress: Optional[StatusProperty] = None
    priority: Optional[SelectProperty] = None
    deadline: Optional[DateProperty] = None
    tags: Optional[MultiSelectProperty] = None

class NotionAction(BaseModel):
    action: Literal["create", "update", "archive"] = Field(description="The type of action to perform.")
    data: Optional[ActionData] = Field(None, description="The data payload for 'create' or 'update' actions.")
    page_id: Optional[str] = Field(None, description="REQUIRED for 'update' and 'archive' actions: The ID of the page.")

class ActionList(RootModel[List[NotionAction]]):
    root: List[NotionAction]

# --- LLM Service with manually controlled prompt ---

class LLMService:
    def __init__(self, prompt_template_path: str):
        self.model = ChatGoogleGenerativeAI(model=settings.GEMINI_MODEL, google_api_key=settings.GOOGLE_API_KEY)
        self.parser = PydanticOutputParser(pydantic_object=ActionList)
        
        try:
            with open(prompt_template_path, 'r', encoding='utf-8') as f:
                template_string = f.read()
            
            self.prompt_template = PromptTemplate(
                template=template_string,
                input_variables=["schema", "today", "thoughts"]
            )
        except FileNotFoundError:
            logger.critical(f"Prompt template file not found at: {prompt_template_path}")
            raise

    async def process_thoughts(self, thoughts: list[str], notion_schema: dict) -> list[dict]:
        if not thoughts:
            return []
            
        concatenated_thoughts = "\n\n---\n\n".join(thoughts)
        schema_as_string = json.dumps(notion_schema, indent=2)
        timezone = pytz.timezone(settings.TIMEZONE)
        current_date = datetime.now(timezone).strftime("%Y-%m-%d")

        chain = self.prompt_template | self.model
        
        final_prompt_str = self.prompt_template.format(
            schema=schema_as_string,
            today=current_date,
            thoughts=concatenated_thoughts
        )
        logger.info("--- FINAL PROMPT SENT TO LLM ---\n%s\n---------------------------------", final_prompt_str)
        
        logger.info(f"Sending a batch of {len(thoughts)} thoughts to the LLM...")
        
        try:
            response = await chain.ainvoke({
                "schema": schema_as_string,
                "today": current_date,
                "thoughts": concatenated_thoughts
            })
            
            logger.info("--- RAW LLM RESPONSE ---\n%s\n------------------------", response.content)

            parsed_response = self.parser.parse(response.content)
            
            actions_list = parsed_response.root
            logger.info(f"LLM returned {len(actions_list)} validated actions.")
            return [action.model_dump(exclude_none=True) for action in actions_list]

        except Exception as e:
            logger.error(f"Failed to invoke LLM or parse/validate response: {e}", exc_info=True)
            return []