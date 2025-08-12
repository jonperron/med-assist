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
    Placeholder function to simulate saving a file.
    In a real application, this would handle the file storage logic.

    :param file_id: The unique identifier for the file.
    :param file: The uploaded file.
    :return: True if the file was saved successfully, False otherwise.
    """

    return await file_handler.extract_text(file_id, file)
