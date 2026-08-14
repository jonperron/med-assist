from abc import ABC, abstractmethod
from typing import Dict, List, Optional, TYPE_CHECKING
from uuid import UUID

if TYPE_CHECKING:
    from app.schemas.extraction import EntityDetail


class TextRepositoryInterface(ABC):
    """Abstract interface for document repository operations."""

    @abstractmethod
    async def save_text(self, file_id: UUID, text: str) -> None:
        """Save extracted text with file ID."""

    @abstractmethod
    async def get_text(self, file_id: UUID) -> Optional[str]:
        """Retrieve text by file ID."""

    @abstractmethod
    async def save_entities(
        self, file_id: UUID, entities: Dict[str, List["EntityDetail"]]
    ) -> None:
        """Save the categorised entities extracted from a document."""

    @abstractmethod
    async def get_entities(
        self, file_id: UUID
    ) -> Optional[Dict[str, List["EntityDetail"]]]:
        """Retrieve the stored entities of a document, or None if it is gone."""

    @abstractmethod
    async def get_document_ttl(self, file_id: UUID) -> Optional[int]:
        """Seconds left before the stored document expires, or None if it is gone."""

    @abstractmethod
    async def delete_document(self, file_id: UUID) -> bool:
        """Delete everything stored for a document. True when something was removed."""

    @abstractmethod
    async def save_batch(self, batch_id: UUID, file_ids: list[str]) -> None:
        """Save batch information."""
