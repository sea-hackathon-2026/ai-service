"""
AI Service - Configuration module.

Loads all settings from environment variables using Pydantic Settings.
Supports .env files for local development.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List, Tuple

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ──
    app_name: str = "AI-Service"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    # ── Server ──
    host: str = "0.0.0.0"
    port: int = 8000

    # ── Database ──
    database_url: str = "sqlite+aiosqlite:///./data/ai_service.db"

    # ── Redis ──
    redis_url: str = "redis://localhost:6379/0"

    # ── CORS ──
    cors_origins: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]

    # ── Auth ──
    api_key_secret: str = "change-me-in-production"
    jwt_secret_key: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60

    # ── AI Models ──
    video_model_id: str = "THUDM/CogVideoX-5b"
    video_model_device: str = "cuda"
    tts_model_id: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    tts_model_device: str = "cuda"

    # â”€â”€ Livestream micro-scene pipeline â”€â”€
    livestream_output_width: int = 720
    livestream_output_height: int = 1280
    livestream_fps: int = 25
    livestream_tts_provider: str = "auto"  # "auto" | "edge" | "silent"
    livestream_tts_voice: str = "vi-VN-HoaiMyNeural"
    livestream_enable_wav2lip: bool = False
    wav2lip_dir: str = "/content/Wav2Lip"
    wav2lip_checkpoint: str = "/content/Wav2Lip/checkpoints/Wav2Lip-SD-GAN.pt"
    wav2lip_resize_factor: int = 2
    wav2lip_pads: Tuple[int, int, int, int] = (0, 20, 0, 0)

    # ── Storage ──
    storage_type: str = "local"  # "local" | "s3"
    storage_local_path: str = "./data/outputs"
    s3_bucket_name: str = ""
    s3_region: str = ""

    # ── WebSocket ──
    ws_max_connections: int = 100
    ws_heartbeat_interval_sec: int = 30

    @property
    def storage_path(self) -> Path:
        """Resolved absolute path for local storage."""
        return Path(self.storage_local_path).resolve()


@lru_cache
def get_settings() -> Settings:
    """Cached singleton for application settings."""
    return Settings()
