"""
Script to cache the HuggingFace embedding model.

This script is intended to be run during the build process to ensure the embedding model
is downloaded and cached, preventing delays during application startup.
"""
import logging
from langchain_huggingface import HuggingFaceEmbeddings

# Configure basic logging as logging_config.py might not be available during build
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')
logging.info("Starting the caching process for the embedding model...")

HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2",
    model_kwargs={'device': 'cpu'}
)

logging.info("Embedding model has been successfully cached.")
