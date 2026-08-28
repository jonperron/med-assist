"""
Service interfaces following Interface Segregation Principle.
"""

from abc import ABC, abstractmethod
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
    async def extract_entities(self, text: str) -> Dict[str, List["EntityDetail"]]:
        """Extract medical entities from text, off the event loop."""

    @abstractmethod
    def get_mapping_info(self) -> Dict[str, Any]:
        """Describe the label mapping backing the extraction."""
