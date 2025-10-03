"""
Pydantic Models for Notion Data Structures.

This module defines the data structures required for creating and updating pages in Notion.
These models are used by the LLMService to generate structured output and by the
NotionService to validate and handle data for API requests.
"""
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, RootModel

# --- Pydantic Models for Notion's Data Structure ---

class NotionContent(BaseModel):
    """Represents the content part of a Notion property."""
    content: str

class TextPart(BaseModel):
    """Represents a text object within a Notion property."""
    text: NotionContent

class TitleProperty(BaseModel):
    """Defines the structure for a 'title' property."""
    title: List[TextPart]

class RichTextProperty(BaseModel):
    """Defines the structure for a 'rich_text' property."""
    rich_text: List[TextPart]

class SelectOption(BaseModel):
    """Represents a single option in a 'select' or 'multi_select' property."""
    name: str

class SelectProperty(BaseModel):
    """Defines the structure for a 'select' property."""
    select: SelectOption

class StatusProperty(BaseModel):
    """Defines the structure for a 'status' property."""
    status: SelectOption

class DateContent(BaseModel):
    """Represents the start date for a 'date' property."""
    start: str

class DateProperty(BaseModel):
    """Defines the structure for a 'date' property."""
    date: DateContent

class MultiSelectProperty(BaseModel):
    """Defines the structure for a 'multi_select' property."""
    multi_select: List[SelectOption]

class ActionData(BaseModel):
    """
    Represents the data payload for a Notion page, containing all possible properties.
    All fields are optional to allow for partial updates.
    """
    Name: Optional[TitleProperty] = None
    description: Optional[RichTextProperty] = None
    progress: Optional[StatusProperty] = None
    priority: Optional[SelectProperty] = None
    deadline: Optional[DateProperty] = None
    tags: Optional[MultiSelectProperty] = None

class NotionAction(BaseModel):
    """
    Defines a single action to be performed on Notion (create, update, or archive).
    This model is the target structure for the LLM's output.
    """
    action: Literal["create", "update", "archive"] = Field(
        description="The type of action to perform."
    )
    data: Optional[ActionData] = Field(
        None, 
        description="The data payload for 'create' or 'update' actions."
    )
    page_id: Optional[str] = Field(
        None, 
        description="REQUIRED for 'update' and 'archive' actions: The ID of the page."
    )

class ActionList(RootModel[List[NotionAction]]):
    """A root model to represent a list of NotionAction objects."""
    root: List[NotionAction]
