"""
Repository pattern implementation for document storage operations.
"""

import json
import logging
from uuid import UUID
from typing import Dict, List, Optional

from pydantic import ValidationError

from app.db.redis import RedisStorage
from app.interfaces.repositories_interfaces import TextRepositoryInterface
from app.schemas.extraction import EntityDetail

logger = logging.getLogger(__name__)


class RedisTextRepository(TextRepositoryInterface):
    """Redis implementation of the document repository."""

    def __init__(self, redis_storage: RedisStorage):
        self._storage = redis_storage

    @staticmethod
    def _text_key(file_id: UUID) -> str:
        return f"doc:{file_id}:text"

    @staticmethod
    def _entities_key(file_id: UUID) -> str:
        return f"doc:{file_id}:entities"

    async def save_text(self, file_id: UUID, text: str) -> None:
        """Save extracted text with file ID."""
        await self._storage.store_value(self._text_key(file_id), text)

    async def get_text(self, file_id: UUID) -> Optional[str]:
        """Retrieve text by file ID."""
        return await self._storage.get_value(self._text_key(file_id))

    async def save_entities(
        self, file_id: UUID, entities: Dict[str, List[EntityDetail]]
    ) -> None:
        """Save the categorised entities extracted from a document."""
        payload = {
            category: [entity.model_dump(mode="json") for entity in details]
            for category, details in entities.items()
        }
        await self._storage.store_value(
            self._entities_key(file_id), json.dumps(payload)
        )

    async def get_entities(
        self, file_id: UUID
    ) -> Optional[Dict[str, List[EntityDetail]]]:
        """Retrieve the stored entities of a document, or None if it is gone."""
        raw = await self._storage.get_value(self._entities_key(file_id))
        if raw is None:
            return None

        try:
            payload = json.loads(raw)
            return {
                category: [EntityDetail(**entity) for entity in details]
                for category, details in payload.items()
            }
        except (json.JSONDecodeError, TypeError, AttributeError, ValidationError):
            # A stored payload we cannot read is indistinguishable from a
            # missing one for the caller. The message stays free of content.
            logger.error("Stored entities for document %s are unreadable", file_id)
            return None

    async def get_document_ttl(self, file_id: UUID) -> Optional[int]:
        """Seconds left before the stored document expires, or None if it is gone."""
        return await self._storage.get_ttl(self._entities_key(file_id))

    async def delete_document(self, file_id: UUID) -> bool:
        """Delete text and entities. True when something was removed."""
        return await self._storage.delete_value(
            self._entities_key(file_id), self._text_key(file_id)
        )

    async def save_batch(self, batch_id: UUID, file_ids: list[str]) -> None:
        """Save batch information."""
        await self._storage.store_value(f"batch:{batch_id}", json.dumps(file_ids))
