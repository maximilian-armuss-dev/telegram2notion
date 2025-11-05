"""
Configuration management for the application.

This module defines the Settings class, which loads and validates application settings
from environment variables and a .env file. It centralizes configuration, making the
application more portable and easier to manage.
"""
from ipaddress import ip_network
from pathlib import Path
from urllib.parse import urlparse
from typing import List
from pydantic import ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import pytz


class Settings(BaseSettings):
    """Loads and validates all application settings from the environment."""

    _VALID_LOG_LEVELS = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}

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
    GEMINI_MODEL: str
    GLADIA_API_URL: str
    GLADIA_POLLING_INTERVAL_SECONDS: int
    GLADIA_MAX_CONCURRENT_TRANSCRIPTIONS: int
    GLADIA_MAX_TRANSCRIPTIONS_PER_HOUR: int
    GLADIA_RATE_LIMIT_WINDOW_SECONDS: int
    GLADIA_RATE_LIMIT_COOLDOWN_SECONDS: int
    # --- RAG (Retrieval-Augmented Generation) ---
    RAG_TOP_K_PER_THOUGHT: int
    # --- Webhook Settings ---
    WEBHOOK_ENABLED: bool
    WEBHOOK_URL: str
    WEBHOOK_HOST: str
    WEBHOOK_PORT: int
    WEBHOOK_SECRET_TOKEN: str
    WEBHOOK_SECRET_LENGTH: int
    TELEGRAM_ALLOWED_CIDRS: List[str]
    STARTUP_POLLING_MAX_RUNS: int
    WEBHOOK_UPDATE_CACHE_SIZE: int
    # --- File Paths & State Management ---
    PROMPT_GEMINI_MAIN_PATH: str
    PROMPT_THOUGHT_STRUCTURING_PATH: str
    STATE_FILE_PATH: str
    # --- General ---
    TIMEZONE: str
    LOG_LEVEL: str

    @model_validator(mode="after")
    def _validate_settings(self) -> "Settings":
        """
        Performs cross-field validation for settings that depend on each other.
        Returns:
            Settings: The validated settings instance.
        Raises:
            ValueError: When critical configuration is missing or invalid.
        """
        if not self.TELEGRAM_BOT_TOKEN.strip():
            raise ValueError("TELEGRAM_BOT_TOKEN must be a non-empty string.")
        if not self.GLADIA_API_KEY.strip():
            raise ValueError("GLADIA_API_KEY must be a non-empty string.")
        if not self.GOOGLE_API_KEY.strip():
            raise ValueError("GOOGLE_API_KEY must be a non-empty string.")
        if not self.NOTION_API_KEY.strip():
            raise ValueError("NOTION_API_KEY must be a non-empty string.")
        if not self.NOTION_DATABASE_ID.strip():
            raise ValueError("NOTION_DATABASE_ID must be a non-empty string.")
        if not self.GEMINI_MODEL.strip():
            raise ValueError("GEMINI_MODEL must be a non-empty string.")
        gladia_url = urlparse(self.GLADIA_API_URL)
        if gladia_url.scheme not in {"http", "https"} or not gladia_url.netloc:
            raise ValueError("GLADIA_API_URL must be a valid HTTP or HTTPS URL.")
        if self.GLADIA_POLLING_INTERVAL_SECONDS <= 0:
            raise ValueError("GLADIA_POLLING_INTERVAL_SECONDS must be greater than zero.")
        if self.GLADIA_MAX_CONCURRENT_TRANSCRIPTIONS <= 0:
            raise ValueError("GLADIA_MAX_CONCURRENT_TRANSCRIPTIONS must be greater than zero.")
        if self.GLADIA_MAX_TRANSCRIPTIONS_PER_HOUR < 0:
            raise ValueError("GLADIA_MAX_TRANSCRIPTIONS_PER_HOUR must be zero or greater.")
        if self.GLADIA_RATE_LIMIT_WINDOW_SECONDS <= 0:
            raise ValueError("GLADIA_RATE_LIMIT_WINDOW_SECONDS must be greater than zero.")
        if self.GLADIA_RATE_LIMIT_COOLDOWN_SECONDS < 0:
            raise ValueError("GLADIA_RATE_LIMIT_COOLDOWN_SECONDS must be zero or greater.")
        if self.RAG_TOP_K_PER_THOUGHT <= 0:
            raise ValueError("RAG_TOP_K_PER_THOUGHT must be greater than zero.")
        if self.STARTUP_POLLING_MAX_RUNS < 0:
            raise ValueError("STARTUP_POLLING_MAX_RUNS must be greater than or equal to zero.")
        if self.WEBHOOK_UPDATE_CACHE_SIZE <= 0:
            raise ValueError("WEBHOOK_UPDATE_CACHE_SIZE must be greater than zero.")
        if self.WEBHOOK_SECRET_LENGTH <= 0:
            raise ValueError("WEBHOOK_SECRET_LENGTH must be greater than zero.")
        if not self.TELEGRAM_ALLOWED_CIDRS:
            raise ValueError("TELEGRAM_ALLOWED_CIDRS must contain at least one CIDR range.")
        for cidr in self.TELEGRAM_ALLOWED_CIDRS:
            try:
                ip_network(cidr)
            except ValueError as error:
                raise ValueError(f"Invalid CIDR entry in TELEGRAM_ALLOWED_CIDRS: {error}") from error
        webhook_url = urlparse(self.WEBHOOK_URL)
        if webhook_url.scheme not in {"http", "https"} or not webhook_url.netloc:
            raise ValueError("WEBHOOK_URL must be a valid HTTP or HTTPS URL.")
        if not self.WEBHOOK_HOST.strip():
            raise ValueError("WEBHOOK_HOST must be a non-empty string.")
        if not 1 <= self.WEBHOOK_PORT <= 65535:
            raise ValueError("WEBHOOK_PORT must be within the range 1-65535.")
        if not self.WEBHOOK_SECRET_TOKEN.strip():
            raise ValueError("WEBHOOK_SECRET_TOKEN must be a non-empty string.")
        if len(self.WEBHOOK_SECRET_TOKEN) < self.WEBHOOK_SECRET_LENGTH:
            raise ValueError("WEBHOOK_SECRET_TOKEN must be at least WEBHOOK_SECRET_LENGTH characters long.")
        if self.WEBHOOK_ENABLED and not self.WEBHOOK_URL:
            raise ValueError("WEBHOOK_URL must be set when WEBHOOK_ENABLED is true.")
        prompt_paths = (
            ("PROMPT_GEMINI_MAIN_PATH", self.PROMPT_GEMINI_MAIN_PATH),
            ("PROMPT_THOUGHT_STRUCTURING_PATH", self.PROMPT_THOUGHT_STRUCTURING_PATH),
        )
        for name, value in prompt_paths:
            if not value.strip():
                raise ValueError(f"{name} must be a non-empty string.")
            if not Path(value).exists():
                raise ValueError(f"{name} points to a missing file: {value}")
        if not self.STATE_FILE_PATH.strip():
            raise ValueError("STATE_FILE_PATH must be a non-empty string.")
        timezone_name = self.TIMEZONE.strip()
        if not timezone_name:
            raise ValueError("TIMEZONE must be a non-empty string.")
        try:
            pytz.timezone(timezone_name)
        except pytz.UnknownTimeZoneError as error:
            raise ValueError(f"TIMEZONE must be a valid IANA timezone: {error}") from error
        log_level = self.LOG_LEVEL.strip().upper()
        if log_level not in self._VALID_LOG_LEVELS:
            raise ValueError(
                f"LOG_LEVEL must be one of {sorted(self._VALID_LOG_LEVELS)}, got '{self.LOG_LEVEL}'."
            )
        return self


try:
    settings = Settings()
except ValidationError as error:
    raise RuntimeError(f"Invalid application configuration: {error}") from error
