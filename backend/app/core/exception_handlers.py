"""
Global exception handlers for the Med-Assist application.
"""

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    MedAssistBaseException,
    FileProcessingError,
    ValidationError,
    StorageError,
)


async def med_assist_exception_handler(
    _request: Request, exc: MedAssistBaseException
) -> JSONResponse:
    """Handle custom Med-Assist exceptions."""
    return JSONResponse(
        status_code=500,
        content={
            "message": exc.message,
            "error_code": exc.error_code,
            "type": exc.__class__.__name__,
        },
    )


async def file_processing_exception_handler(
    _request: Request, exc: FileProcessingError
) -> JSONResponse:
    """Handle file processing errors."""
    return JSONResponse(
        status_code=422,
        content={
            "message": exc.message,
            "error_code": exc.error_code,
            "type": "file_processing_error",
        },
    )


async def validation_exception_handler(
    _request: Request, exc: ValidationError
) -> JSONResponse:
    """Handle validation errors."""
    return JSONResponse(
        status_code=400,
        content={
            "message": exc.message,
            "error_code": exc.error_code,
            "type": "validation_error",
        },
    )


async def storage_exception_handler(
    _request: Request, exc: StorageError
) -> JSONResponse:
    """Handle storage errors."""
    return JSONResponse(
        status_code=503,
        content={
            "message": exc.message,
            "error_code": exc.error_code,
            "type": "storage_error",
        },
    )
