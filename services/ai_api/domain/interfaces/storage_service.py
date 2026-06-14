"""
IStorageService - Abstract interface for file storage.

Abstracts away where generated files (videos, audio) are stored,
allowing easy swapping between local filesystem, S3, MinIO, etc.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class IStorageService(ABC):
    """Port for file storage services."""

    @abstractmethod
    async def save(
        self,
        data: bytes,
        filename: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Save binary data and return its accessible URL/path.

        Args:
            data: Binary file content.
            filename: Desired filename (may include subdirectory path).
            content_type: MIME type of the data.

        Returns:
            URL or path to access the saved file.
        """
        ...

    @abstractmethod
    async def get_url(self, filename: str) -> str | None:
        """Get the accessible URL for a stored file, or None if not found."""
        ...

    @abstractmethod
    async def delete(self, filename: str) -> bool:
        """Delete a file from storage. Returns True if deleted."""
        ...

    @abstractmethod
    async def exists(self, filename: str) -> bool:
        """Check if a file exists in storage."""
        ...
