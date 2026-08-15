from typing import Optional
from uuid import UUID

from fastapi import Depends, UploadFile

from app.core.dependencies import get_file_handler
from app.services.file_handler import FileHandler


async def save_file(
    file_id: UUID,
    file: UploadFile,
    file_handler: FileHandler = Depends(get_file_handler),
    pseudonymize: Optional[bool] = None,
) -> bool:
    """
    Save file using FastAPI dependency injection.

    :param file_id: The unique identifier for the file.
    :param file: The uploaded file.
    :param file_handler: Injected file handler dependency.
    :param pseudonymize: Override the configured pseudonymisation default.
    :return: True if the file was saved successfully, False otherwise.
    """
    return await file_handler.process_file(file_id, file, pseudonymize)

