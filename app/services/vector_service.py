import logging
from typing import List, Dict
from langchain_community.docstore.document import Document
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings

logger = logging.getLogger(__name__)

class VectorService:
    """Handles the creation and querying of a vector index for Notion pages."""

    def __init__(self):
        """Initializes the embedding model."""
        # Use a local, open-source model for embeddings
        self.embeddings = HuggingFaceEmbeddings(
            model_name="all-MiniLM-L6-v2",
            model_kwargs={'device': 'cpu'}
        )
        self.index = None

    def build_index_from_notion_pages(self, pages: List[Dict[str, str]]):
        """
        Builds a FAISS vector index from a list of Notion pages.

        Args:
            pages: A list of dictionaries, where each dictionary
                   represents a page and has 'page_id' and 'content' keys.
        """
        if not pages:
            logger.warning("No pages provided to build the vector index. The index will be empty.")
            self.index = None
            return

        logger.info(f"Building vector index from {len(pages)} Notion pages...")
        documents = [
            Document(page_content=page['content'], metadata={'page_id': page['page_id']})
            for page in pages
        ]
        
        try:
            self.index = FAISS.from_documents(documents, self.embeddings)
            logger.info("Successfully built the vector index.")
        except Exception as e:
            logger.error(f"Failed to build FAISS index: {e}", exc_info=True)
            self.index = None

    def search(self, query: str, k: int = 5) -> List[Document]:
        """
        Searches the vector index for the most similar documents to a query.

        Args:
            query: The text to search for.
            k: The number of similar documents to return.

        Returns:
            A list of Document objects, each containing page_content and metadata.
        """
        if not self.index:
            logger.warning("Search attempted but the vector index is not built.")
            return []

        logger.info(f"Performing vector search for query: '{query[:50]}...'")
        try:
            results = self.index.similarity_search(query, k=k)
            logger.info(f"Vector search returned {len(results)} results.")
            return results
        except Exception as e:
            logger.error(f"Failed during vector search: {e}", exc_info=True)
            return []
