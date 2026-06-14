"""Configuration for the RAG service."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed service settings."""

    service_name: str = "rag-service"
    service_version: str = "1.0.0"
    log_level: str = "INFO"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    knowledge_base_path: Path = Path(__file__).parent / "resources" / "knowledge_base.json"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="RAG_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide immutable settings object."""

    return Settings()
