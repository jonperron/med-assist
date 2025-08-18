from uuid import UUID

from fastapi import UploadFile

from app.db.redis import RedisStorage
from app.services.text_extractor import TextExtractor


class FileHandler:
    """
    Handles file operations such as saving and retrieving files.
    This class is a placeholder for future file handling logic.
    """

    def __init__(self, redis_storage: RedisStorage) -> None:
        self.extractor = TextExtractor()
        self.storage = redis_storage

    async def save_extracted_text(self, file_uuid: UUID, extracted_text: str) -> None:
        """
        Saves the extracted text to the Redis storage.

        :param filename: The name of the file from which text was extracted.
        :param extracted_text: The text extracted from the file.
        """
        await self.storage.store_value(str(file_uuid), extracted_text)

    async def extract_text(self, file_id: UUID, file: UploadFile) -> bool:
        """
        Extracts text from the document based on its file type.

        :param file_id: The unique identified of the uploaded file.
        :param file: The uploaded file.
        :return: Extracted text as a string.
        """
        text = await self.extractor.extract_text(file)
        if text:
            await self.save_extracted_text(file_id, text)
            return True

        return False

    async def save_batch(self, batch_id: UUID, file_ids: list[str]) -> bool:
        """
        Save the identifier of a batch of files with corresponding file ids.

        :param batch_id: The unique identifier for the batch of files.
        :param file_ids: The list of unique identifiers for the uploaded files
        :return: True if batch was saved successfully
        """
        await self.storage.store_value(str(batch_id), str(file_ids))

        return True
