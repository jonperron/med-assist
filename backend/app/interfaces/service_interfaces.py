"""
Service interfaces following Interface Segregation Principle.
"""

from abc import ABC, abstractmethod
from uuid import UUID
from typing import Dict, List, Optional

from fastapi import UploadFile


class TextExtractionServiceInterface(ABC):
    """Interface for text extraction operations."""

    @abstractmethod
    async def extract_text(self, file: UploadFile) -> Optional[str]:
        """Extract text from uploaded file."""


class EntityExtractionServiceInterface(ABC):
    """Interface for entity extraction operations."""

    @abstractmethod
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract medical entities from text."""


class FileProcessingServiceInterface(ABC):
    """Interface for file processing operations."""

    @abstractmethod
    async def process_file(self, file_id: UUID, file: UploadFile) -> bool:
        """Process uploaded file and save extracted text."""

    @abstractmethod
    async def process_batch(self, batch_id: UUID, file_ids: list[str]) -> bool:
        """Process batch of files."""
