from uuid import UUID

from fastapi import UploadFile

from app.repositories.text_repository import TextRepositoryInterface
from app.services.text_extractor import TextExtractor
from app.interfaces.service_interfaces import FileProcessingServiceInterface


class FileHandler(FileProcessingServiceInterface):
    """
    Handles file operations such as saving and retrieving files.
    Implements the Repository pattern for data access.
    """

    def __init__(self, text_repository: TextRepositoryInterface) -> None:
        self.extractor = TextExtractor()
        self.text_repository = text_repository

    async def process_file(self, file_id: UUID, file: UploadFile) -> bool:
        """
        Process uploaded file and save extracted text.

        :param file_id: The unique identifier of the uploaded file.
        :param file: The uploaded file.
        :return: True if processing was successful, False otherwise.
        """
        text = await self.extractor.extract_text(file)
        if text:
            await self.text_repository.save_text(file_id, text)
            return True
        return False

    async def process_batch(self, batch_id: UUID, file_ids: list[str]) -> bool:
        """
        Process batch of files.

        :param batch_id: The unique identifier for the batch of files.
        :param file_ids: The list of unique identifiers for the uploaded files
        :return: True if batch was processed successfully
        """
        await self.text_repository.save_batch(batch_id, file_ids)
        return True
