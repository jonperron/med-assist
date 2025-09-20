from abc import ABC, abstractmethod
from typing import Optional
from uuid import UUID


class TextRepositoryInterface(ABC):
    """Abstract interface for text repository operations."""

    @abstractmethod
    async def save_text(self, file_id: UUID, text: str) -> None:
        """Save extracted text with file ID."""

    @abstractmethod
    async def get_text(self, file_id: UUID) -> Optional[str]:
        """Retrieve text by file ID."""

    @abstractmethod
    async def save_batch(self, batch_id: UUID, file_ids: list[str]) -> None:
        """Save batch information."""
