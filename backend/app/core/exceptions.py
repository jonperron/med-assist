"""
Custom exceptions for the Med-Assist application.
"""

from typing import Optional


class MedAssistBaseException(Exception):
    """Base exception class for Med-Assist application."""

    def __init__(self, message: str, error_code: Optional[str] = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


class FileProcessingError(MedAssistBaseException):
    """Exception raised when file processing fails."""


class TextExtractionError(MedAssistBaseException):
    """Exception raised when text extraction fails."""


class EntityExtractionError(MedAssistBaseException):
    """Exception raised when entity extraction fails."""


class ValidationError(MedAssistBaseException):
    """Exception raised when validation fails."""


class StorageError(MedAssistBaseException):
    """Exception raised when storage operations fail."""
