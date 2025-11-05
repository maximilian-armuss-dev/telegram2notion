"""
Service layer for interacting with the Notion API.

This module provides a simplified interface for performing CRUD (Create, Read, Update, Delete)
operations on a Notion database. It encapsulates the notion-client SDK and handles
schema retrieval, page creation, updates, and archival.
"""
import logging
from typing import Dict, Any, List
from notion_client import AsyncClient
from notion_client.errors import APIResponseError
from app.config import settings

logger = logging.getLogger(__name__)

class NotionService:
    """A client to interact with the Notion API."""

    def __init__(self) -> None:
        """Initializes the Notion async client with the API key from settings."""
        self.client = AsyncClient(auth=settings.NOTION_API_KEY)
        self.database_id = settings.NOTION_DATABASE_ID

    async def _query_database(self, **params: Any) -> Dict[str, Any]:
        """
        Queries the configured database using the notion-client API compatible with multiple versions.
        Args:
            params: Additional parameters forwarded to the query endpoint.
        Returns:
            The raw Notion API response.
        Raises:
            RuntimeError: If neither query method is available on the client.
        """
        request_params = {"database_id": self.database_id, **params}
        query_callable = getattr(self.client.databases, "query", None)
        if callable(query_callable):
            logger.debug("Querying Notion database via databases.query endpoint.")
            try:
                return await query_callable(**request_params)
            except TypeError:
                return await query_callable(self.database_id, **params)
        query_database_callable = getattr(self.client.databases, "query_database", None)
        if callable(query_database_callable):
            logger.debug("Querying Notion database via databases.query_database endpoint.")
            try:
                return await query_database_callable(**request_params)
            except TypeError:
                return await query_database_callable(self.database_id, **params)
        raise RuntimeError("Unsupported notion-client version: no query method available.")

    async def get_database_schema(self) -> Dict[str, Any]:
        """
        Retrieves and simplifies the schema of the configured Notion database.
        This method extracts only the essential information (property name, type, and options)
        to provide a clean schema for the LLM.
        Returns:
            A dictionary representing the simplified database schema.
        Raises:
            APIResponseError: If the database retrieval fails.
        """
        logger.info(f"Retrieving schema for Notion database ID: {self.database_id}")
        try:
            db_response = await self.client.databases.retrieve(database_id=self.database_id)
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
            logger.info("Successfully retrieved and simplified database schema.")
            return simplified_schema
        except APIResponseError as e:
            logger.error(f"Failed to retrieve Notion database schema: {e}", exc_info=True)
            raise

    async def create_page(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Creates a new page in the Notion database.
        Args:
            data: A dictionary representing the properties of the new page.
        Returns:
            The API response from Notion upon successful creation.
        Raises:
            APIResponseError: If the page creation fails.
        """
        logger.info("Creating a new page in Notion.")
        logger.debug(f"Page data: {data}")
        try:
            response = await self.client.pages.create(
                parent={"database_id": self.database_id},
                properties=data
            )
            logger.info(f"Successfully created Notion page with ID: {response['id']}")
            return response
        except APIResponseError as e:
            logger.error(f"Failed to create Notion page with data {data}: {e}", exc_info=True)
            raise

    async def update_page(self, page_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Updates an existing page in Notion.
        Args:
            page_id: The ID of the page to update.
            data: A dictionary containing the properties to be updated.
        Returns:
            The API response from Notion upon successful update.
        Raises:
            APIResponseError: If the page update fails.
        """
        logger.info(f"Updating Notion page with ID: {page_id}")
        logger.debug(f"Update data for page {page_id}: {data}")
        try:
            response = await self.client.pages.update(
                page_id=page_id,
                properties=data
            )
            logger.info(f"Successfully updated Notion page with ID: {page_id}")
            return response
        except APIResponseError as e:
            logger.error(f"Failed to update Notion page {page_id} with data {data}: {e}", exc_info=True)
            raise

    async def archive_page(self, page_id: str) -> Dict[str, Any]:
        """
        Archives a page in Notion, effectively deleting it from the active view.
        Args:
            page_id: The ID of the page to archive.
        Returns:
            The API response from Notion upon successful archival.
        Raises:
            APIResponseError: If the page archival fails.
        """
        logger.info(f"Archiving Notion page with ID: {page_id}")
        try:
            response = await self.client.pages.update(
                page_id=page_id,
                archived=True
            )
            logger.info(f"Successfully archived Notion page with ID: {page_id}")
            return response
        except APIResponseError as e:
            logger.error(f"Failed to archive Notion page {page_id}: {e}", exc_info=True)
            raise

    async def query_all_pages(self) -> List[Dict[str, str]]:
        """
        Queries all non-"Done" pages from the database for RAG context.
        Handles pagination to retrieve all relevant pages.
        Returns:
            A list of dictionaries, each containing the 'page_id' and 'content'
            of a Notion page.
        """
        logger.info("Querying all pages from Notion database for RAG...")
        all_pages_content = []
        has_more = True
        start_cursor = None
        while has_more:
            try:
                query_params: Dict[str, Any] = {
                    "filter": {
                        "property": "progress",
                        "status": {"does_not_equal": "Done"},
                    },
                }
                if start_cursor:
                    query_params["start_cursor"] = start_cursor
                response = await self._query_database(**query_params)
                results = response.get("results", [])
                for page in results:
                    page_id = page.get("id")
                    properties = page.get("properties", {})
                    content = self.extract_text_from_properties(properties)
                    if page_id and content:
                        all_pages_content.append({"page_id": page_id, "content": content})
                has_more = response.get("has_more", False)
                start_cursor = response.get("next_cursor")
                logger.info(f"Retrieved {len(results)} pages. Has more: {has_more}")
            except APIResponseError as e:
                logger.error(f"An error occurred while querying Notion database: {e}", exc_info=True)
                break
            except RuntimeError as e:
                logger.error(f"Failed to locate the Notion database query endpoint: {e}", exc_info=True)
                break
        logger.info(f"Total pages retrieved for RAG context: {len(all_pages_content)}")
        return all_pages_content

    @staticmethod
    def extract_text_from_properties(properties: Dict[str, Any]) -> str:
        """
        Extracts and formats key properties from a Notion page into a single string.
        This static method is designed to be reusable for creating consistent text
        representations of Notion pages, both from API responses and from structured
        dictionaries generated by the LLM.
        Args:
            properties: A dictionary of Notion page properties.
        Returns:
            A formatted string combining the content of key properties.
        """
        data = {}
        for prop_name, prop_value in properties.items():
            name_lower = prop_name.lower()
            if not isinstance(prop_value, dict):
                continue
            prop_type = prop_value.get("type")
            if name_lower == "description" and prop_type == "rich_text":
                texts = [item.get("plain_text", "") for item in prop_value.get("rich_text", [])]
                data['Description'] = "".join(texts).strip()
            elif name_lower == "progress" and prop_type == "status" and prop_value.get("status"):
                data['Progress'] = prop_value["status"].get("name", "")
            elif name_lower == "priority" and prop_type == "select" and prop_value.get("select"):
                data['Priority'] = prop_value["select"].get("name", "")
            elif name_lower == "deadline" and prop_type == "date" and prop_value.get("date"):
                data['Deadline'] = prop_value["date"].get("start", "")
            elif name_lower == "tags" and prop_type == "multi_select":
                tags = [
                    tag.get("name", "")
                    for tag in prop_value.get("multi_select", [])
                    if tag.get("name")
                ]
                if tags:
                    data['Tags'] = ", ".join(tags)
        return "\n".join([f"{key}: {value}" for key, value in data.items() if value])
