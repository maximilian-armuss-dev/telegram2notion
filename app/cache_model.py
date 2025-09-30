import logging
from langchain_huggingface import HuggingFaceEmbeddings

# Not using logging_config.py as this script will already run while building
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')

logging.info("Start caching of the embedding model...")

HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2",
    model_kwargs={'device': 'cpu'}
)

logging.info("Embedding model has been successfully cached.")
