"""
Configuration management for the application.

This module defines the Settings class, which loads and validates application settings
from environment variables and a .env file. It centralizes configuration, making the
application more portable and easier to manage.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Loads and validates all application settings from the environment."""

    # --- Environment File Configuration ---
    model_config: SettingsConfigDict = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )
    # --- Core API Keys & Identifiers ---
    TELEGRAM_BOT_TOKEN: str
    GLADIA_API_KEY: str
    GOOGLE_API_KEY: str
    NOTION_API_KEY: str
    NOTION_DATABASE_ID: str
    # --- LLM & AI Services ---
    GEMINI_MODEL: str = "gemini-2.5-flash"
    GLADIA_API_URL: str = "https://api.gladia.io/v2"
    GLADIA_POLLING_INTERVAL_SECONDS: int = 10
    # --- RAG (Retrieval-Augmented Generation) ---
    RAG_TOP_K_PER_THOUGHT: int = 3
    # --- File Paths & State Management ---
    PROMPT_GEMINI_MAIN_PATH: str = "prompts/gemini_prompt.md"
    PROMPT_THOUGHT_STRUCTURING_PATH: str = "prompts/thought_structuring_prompt.md"
    STATE_FILE_PATH: str = "processed_update_ids.json"
    # --- General ---
    TIMEZONE: str = "Europe/Berlin"
    LOG_LEVEL: str = "INFO"


settings = Settings()
