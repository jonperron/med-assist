"""
Service interfaces following Interface Segregation Principle.
"""

from abc import ABC, abstractmethod
from uuid import UUID
from typing import Any, Dict, List, Optional

from fastapi import UploadFile

# Import TYPE_CHECKING to avoid circular imports
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas.extraction import EntityDetail


class TextExtractionServiceInterface(ABC):
    """Interface for text extraction operations."""

    @abstractmethod
    async def extract_text(self, file: UploadFile) -> Optional[str]:
        """Extract text from uploaded file."""


class EntityExtractionServiceInterface(ABC):
    """Interface for entity extraction operations."""

    @abstractmethod
    def extract_entities(self, text: str) -> Dict[str, List["EntityDetail"]]:
        """Extract medical entities from text."""

    @abstractmethod
    def get_mapping_info(self) -> Dict[str, Any]:
        """Describe the label mapping backing the extraction."""


class FileProcessingServiceInterface(ABC):
    """Interface for file processing operations."""

    @abstractmethod
    async def process_file(
        self, file_id: UUID, file: UploadFile, pseudonymize: Optional[bool] = None
    ) -> bool:
        """Process uploaded file and persist what the deployment allows."""

    @abstractmethod
    async def process_batch(self, batch_id: UUID, file_ids: list[str]) -> bool:
        """Process batch of files."""
