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

    async def query_all_pages(self) -> list[dict]:
        """
        Queries all pages from the Notion database and extracts their content.
        Handles pagination to retrieve more than 100 pages.
        """
        logger.info("Querying all pages from Notion database...")
        all_pages_content = []
        has_more = True
        start_cursor = None

        while has_more:
            try:
                response = await self.client.databases.query(
                    database_id=settings.NOTION_DATABASE_ID,
                    start_cursor=start_cursor,
                    filter={
                        "property": "progress",
                        "status": {
                            "does_not_equal": "Done"
                        }
                    }
                )
                results = response.get("results", [])
                
                for page in results:
                    page_id = page.get("id")
                    properties = page.get("properties", {})
                    content = self._extract_text_from_properties(properties)
                    
                    if page_id and content:
                        all_pages_content.append({"page_id": page_id, "content": content})

                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")
                logger.info(f"Retrieved {len(results)} pages. Has more: {has_more}")

            except Exception as e:
                logger.error(f"An error occurred while querying Notion database: {e}", exc_info=True)
                break 
        
        logger.info(f"Total pages retrieved and processed: {len(all_pages_content)}")
        return all_pages_content

    def _extract_text_from_properties(self, properties: dict) -> str:
        """
        Extracts key properties from a Notion page and formats them into a single
        string for embedding. Includes description, progress, priority, deadline, and tags.
        The title is intentionally excluded to avoid redundancy.
        """
        data = {}
        
        for prop_name, prop_value in properties.items():
            prop_type = prop_value.get("type")
            
            # Use lowercased property name for consistent matching
            name_lower = prop_name.lower()

            if name_lower == "description" and prop_type == "rich_text":
                texts = [item.get("plain_text", "") for item in prop_value.get("rich_text", [])]
                data['Description'] = "".join(texts).strip()

            elif name_lower == "progress" and prop_type == "status":
                if prop_value.get("status"):
                    data['Progress'] = prop_value["status"].get("name", "")

            elif name_lower == "priority" and prop_type == "select":
                if prop_value.get("select"):
                    data['Priority'] = prop_value["select"].get("name", "")

            elif name_lower == "deadline" and prop_type == "date":
                if prop_value.get("date"):
                    data['Deadline'] = prop_value["date"].get("start", "")

            elif name_lower == "tags" and prop_type == "multi_select":
                tags_list = prop_value.get("multi_select", [])
                tags = [tag.get("name", "") for tag in tags_list if tag.get("name")]
                if tags:
                    data['Tags'] = ", ".join(tags)

        # Format the extracted data into a clean, searchable string
        content_parts = [f"{key}: {value}" for key, value in data.items() if value]
        
        return "\n".join(content_parts)
