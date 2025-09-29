import logging
import json
from notion_client import AsyncClient
from app.config import settings

logger = logging.getLogger(__name__)

class NotionService:
    def __init__(self):
        self.client = AsyncClient(auth=settings.NOTION_API_KEY)

    async def get_database_schema(self) -> dict:
        """Retrieves and simplifies the schema of the Notion database."""
        logger.info(f"Retrieving schema for Notion database ID: {settings.NOTION_DATABASE_ID}")
        db_response = await self.client.databases.retrieve(database_id=settings.NOTION_DATABASE_ID)
        properties = db_response.get('properties', {})
        
        simplified_schema = {}
        for key, prop in properties.items():
            prop_name = prop.get('name')
            prop_type = prop.get('type')
            if not prop_name or not prop_type:
                continue
            
            simplified_schema[prop_name] = {'type': prop_type}
            if prop_type in ['select', 'multi_select', 'status']:
                options = prop.get(prop_type, {}).get('options', [])
                if options:
                    simplified_schema[prop_name]['options'] = [opt.get('name') for opt in options]
        return simplified_schema

    async def create_page(self, data: dict):
        """Creates a new page in the Notion database."""
        logger.info(f"Sending following data to Notion create API: \n{json.dumps(data, indent=2)}")
        
        logger.info("Creating a new page in Notion.")
        response = await self.client.pages.create(
            parent={"database_id": settings.NOTION_DATABASE_ID},
            properties=data
        )
        logger.info(f"Successfully created Notion page with ID: {response['id']}")
        return response

    async def update_page(self, page_id: str, data: dict):
        """Updates an existing page in Notion."""
        logger.info(f"Updating Notion page with ID: {page_id}")
        response = await self.client.pages.update(
            page_id=page_id,
            properties=data
        )
        logger.info(f"Successfully updated Notion page with ID: {page_id}")
        return response

    async def archive_page(self, page_id: str):
        """
        Archives a page in Notion, which is the equivalent of deleting it.
        The page can be restored from the trash in Notion if needed.
        """
        logger.info(f"Archiving Notion page with ID: {page_id}")
        response = await self.client.pages.update(
            page_id=page_id,
            archived=True
        )
        logger.info(f"Successfully archived Notion page with ID: {page_id}")
        return response