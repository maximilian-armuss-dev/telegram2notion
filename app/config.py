from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Loads and validates settings from the environment."""
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')
    TELEGRAM_BOT_TOKEN: str
    GLADIA_API_KEY: str
    GOOGLE_API_KEY: str
    NOTION_API_KEY: str
    NOTION_DATABASE_ID: str
    GEMINI_MODEL: str
    TIMEZONE: str

settings = Settings()