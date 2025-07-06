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

    def save_extracted_text(self, filename: str, extracted_text: str) -> None:
        """
        Saves the extracted text to the Redis storage.
        
        :param filename: The name of the file from which text was extracted.
        :param extracted_text: The text extracted from the file.
        """
        self.storage.store_value(filename, extracted_text)

    async def extract_text(self, file: UploadFile) -> bool:
        """
        Extracts text from the document based on its file type.
        
        :param file: The uploaded file.
        :return: Extracted text as a string.
        """
        text = await self.extractor.extract_text(file)
        self.storage.store_value(file.filename, text)
        return True if text else False
