"""
Local filesystem storage adapter.

Implements IStorageService for saving generated files to local disk.
Files are served via FastAPI's StaticFiles mount.
"""

from __future__ import annotations

import logging
from pathlib import Path

import aiofiles

from services.ai_api.domain.interfaces.storage_service import IStorageService

logger = logging.getLogger(__name__)


class LocalStorageService(IStorageService):
    """File storage on the local filesystem."""

    def __init__(self, base_path: str, serve_url_prefix: str = "/outputs") -> None:
        self._base_path = Path(base_path).resolve()
        self._serve_url_prefix = serve_url_prefix.rstrip("/")
        # Ensure base directory exists
        self._base_path.mkdir(parents=True, exist_ok=True)

    async def save(
        self,
        data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Save binary data to local filesystem and return the serve URL."""
        file_path = self._base_path / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)

        async with aiofiles.open(file_path, "wb") as f:
            await f.write(data)

        logger.info("Saved file: %s (%d bytes)", file_path, len(data))
        return f"{self._serve_url_prefix}/{filename}"

    async def get_url(self, filename: str) -> str | None:
        """Get the serve URL for a stored file."""
        file_path = self._base_path / filename
        if file_path.exists():
            return f"{self._serve_url_prefix}/{filename}"
        return None

    async def delete(self, filename: str) -> bool:
        """Delete a file from local storage."""
        file_path = self._base_path / filename
        if file_path.exists():
            file_path.unlink()
            logger.info("Deleted file: %s", file_path)
            return True
        return False

    async def exists(self, filename: str) -> bool:
        """Check if a file exists in local storage."""
        return (self._base_path / filename).exists()
