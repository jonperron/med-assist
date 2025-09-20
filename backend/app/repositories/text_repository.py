"""
Repository pattern implementation for text storage operations.
"""

from uuid import UUID
from typing import Optional

from app.db.redis import RedisStorage
from app.interfaces.repositories_interfaces import TextRepositoryInterface


class RedisTextRepository(TextRepositoryInterface):
    """Redis implementation of text repository."""

    def __init__(self, redis_storage: RedisStorage):
        self._storage = redis_storage

    async def save_text(self, file_id: UUID, text: str) -> None:
        """Save extracted text with file ID."""
        await self._storage.store_value(str(file_id), text)

    async def get_text(self, file_id: UUID) -> Optional[str]:
        """Retrieve text by file ID."""
        return await self._storage.get_value(str(file_id))

    async def save_batch(self, batch_id: UUID, file_ids: list[str]) -> None:
        """Save batch information."""
        await self._storage.store_value(str(batch_id), str(file_ids))
