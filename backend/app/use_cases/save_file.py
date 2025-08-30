from uuid import UUID

from fastapi import Depends, UploadFile

from app.core.dependencies import get_file_handler
from app.services.file_handler import FileHandler


async def save_file(
    file_id: UUID,
    file: UploadFile,
    file_handler: FileHandler = Depends(get_file_handler),
) -> bool:
    """
    Save file using FastAPI dependency injection.

    :param file_id: The unique identifier for the file.
    :param file: The uploaded file.
    :param file_handler: Injected file handler dependency.
    :return: True if the file was saved successfully, False otherwise.
    """
    return await file_handler.process_file(file_id, file)


async def save_batch(
    batch_id: UUID,
    file_ids: list[str],
    file_handler: FileHandler = Depends(get_file_handler),
) -> bool:
    """
    Save batch using FastAPI dependency injection.

    :param batch_id: The unique identifier for the batch of files.
    :param file_ids: The list of unique identified for the uploaded files.
    :param file_handler: Injected file handler dependency.
    :return: True if the batch was saved successfully, False otherwise.
    """
    return await file_handler.process_batch(batch_id, file_ids)
