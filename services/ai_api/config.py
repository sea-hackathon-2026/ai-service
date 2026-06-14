"""Environment-backed configuration for the AI orchestration API."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for HTTP, persistence, storage, and model adapters."""

    app_name: str = "ai-api"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000

    database_url: str = "sqlite+aiosqlite:///./data/ai_service.db"
    cors_origins: Annotated[list[str], NoDecode] = []
    api_key_secret: str = "change-me-in-production"
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    gemini_api_key: str = ""
    genai_prefer_api: bool = True
    genai_imagen_model: str = "imagen-3.0-generate-002"
    genai_veo_model: str = "veo-2.0-generate-001"
    genai_aspect_ratio: str = "16:9"
    genai_use_imagen: bool = False
    genai_skip_wav2lip: bool = True
    genai_enhance_prompt: bool = True

    livestream_output_width: int = 720
    livestream_output_height: int = 1280
    livestream_fps: int = 25
    livestream_tts_provider: str = "auto"
    livestream_tts_voice: str = "vi-VN-HoaiMyNeural"
    livestream_enable_wav2lip: bool = False
    wav2lip_dir: str = "/content/Wav2Lip"
    wav2lip_checkpoint: str = "/content/Wav2Lip/checkpoints/Wav2Lip-SD-GAN.pt"
    wav2lip_resize_factor: int = 2
    wav2lip_pads: tuple[int, int, int, int] = (0, 20, 0, 0)

    storage_local_path: str = "./data/outputs"
    ws_max_connections: int = 100
    ws_heartbeat_interval_sec: int = 30

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="AI_API_",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: object) -> object:
        """Accept a JSON array or a comma-separated environment value."""

        if isinstance(value, str) and value:
            if value.lstrip().startswith("["):
                return json.loads(value)
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def storage_path(self) -> Path:
        return Path(self.storage_local_path).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
