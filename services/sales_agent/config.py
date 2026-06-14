"""Configuration for the sales-agent service."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Model and runtime settings loaded from environment variables."""

    service_name: str = "sales-agent"
    service_version: str = "1.0.0"
    primary_model: str = "gemini-2.0-flash"
    fallback_model: str = "groq/llama-3.3-70b-versatile"
    user_id: str = "live-commerce-user"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="SALES_AGENT_", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
