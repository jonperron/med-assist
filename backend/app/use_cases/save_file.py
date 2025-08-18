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
    :param file_id: The unique identifier for the file.
    :param file: The uploaded file.
    :return: True if the file was saved successfully, False otherwise.
    """

    return await file_handler.extract_text(file_id, file)


async def save_batch(
    batch_id: UUID,
    file_ids: list[str],
    file_handler: FileHandler = Depends(get_file_handler),
) -> bool:
    """
    :param batch_id: The unique identifier for the batch of files.
    :param file_ids: The list of unique identified for the uploaded files
    :return: True if the batch was saved successfully, False otherwise
    """
    return await file_handler.save_batch(batch_id, file_ids)
