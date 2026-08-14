from typing import Dict, List, Optional
from uuid import UUID

from fastapi import UploadFile

from app.core.config import PrivacyConfiguration
from app.interfaces.repositories_interfaces import TextRepositoryInterface
from app.interfaces.service_interfaces import (
    EntityExtractionServiceInterface,
    FileProcessingServiceInterface,
)
from app.schemas.extraction import EntityDetail
from app.services.pseudonymizer import Pseudonymizer
from app.services.text_extractor import TextExtractor


def drop_offsets(
    entities: Dict[str, List[EntityDetail]],
) -> Dict[str, List[EntityDetail]]:
    """Strip start/end offsets, which mean nothing without the text they index."""
    return {
        category: [
            entity.model_copy(update={"start": None, "end": None}) for entity in details
        ]
        for category, details in entities.items()
    }


class FileHandler(FileProcessingServiceInterface):
    """
    Handles file operations such as saving and retrieving files.
    Implements the Repository pattern for data access.
    """

    def __init__(
        self,
        text_repository: TextRepositoryInterface,
        entity_extractor: EntityExtractionServiceInterface,
        privacy_config: PrivacyConfiguration,
        pseudonymizer: Optional[Pseudonymizer] = None,
    ) -> None:
        self.extractor = TextExtractor()
        self.text_repository = text_repository
        self.entity_extractor = entity_extractor
        self.privacy_config = privacy_config
        self.pseudonymizer = pseudonymizer or Pseudonymizer()

    async def process_file(
        self, file_id: UUID, file: UploadFile, pseudonymize: Optional[bool] = None
    ) -> bool:
        """
        Process an uploaded file and persist its entities.

        The document text is analysed in memory and only the categorised
        entities are written, unless the deployment opted into keeping the text.

        :param file_id: The unique identifier of the uploaded file.
        :param file: The uploaded file.
        :param pseudonymize: Ask for masking even when the deployment default is off.
        :return: True if processing was successful, False otherwise.
        """
        text = await self.extractor.extract_text(file)
        if not text:
            return False

        entities = self.entity_extractor.extract_entities(text)

        # A request may ask for masking, never turn a deployment's policy off.
        if self.privacy_config.pseudonymize or bool(pseudonymize):
            text, entities = self.pseudonymizer.mask(text, entities)

        if self.privacy_config.store_document_text:
            await self.text_repository.save_text(file_id, text)
        else:
            entities = drop_offsets(entities)

        await self.text_repository.save_entities(file_id, entities)
        return True

    async def process_batch(self, batch_id: UUID, file_ids: list[str]) -> bool:
        """
        Process batch of files.

        :param batch_id: The unique identifier for the batch of files.
        :param file_ids: The list of unique identifiers for the uploaded files
        :return: True if batch was processed successfully
        """
        await self.text_repository.save_batch(batch_id, file_ids)
        return True
