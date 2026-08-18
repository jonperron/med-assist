from typing import Dict, List, Tuple

from fastapi import UploadFile

from app.interfaces.service_interfaces import (
    EntityExtractionServiceInterface,
    TextExtractionServiceInterface,
)
from app.schemas.extraction import EntityDetail
from app.services.pseudonymizer import Pseudonymizer


async def analyze_document(
    file: UploadFile,
    text_extractor: TextExtractionServiceInterface,
    entity_extractor: EntityExtractionServiceInterface,
    pseudonymizer: Pseudonymizer,
    pseudonymize: bool = False,
) -> Tuple[str, Dict[str, List[EntityDetail]]]:
    """
    Extract text and entities from a document without storing anything.

    :param file: The uploaded file.
    :param text_extractor: The text extraction service.
    :param entity_extractor: The entity extraction service.
    :param pseudonymizer: The service masking patient identifiers.
    :param pseudonymize: Whether to mask detected patient identifiers.
    :return: The (possibly masked) text and its categorised entities.
    :raises ValueError: If no text could be extracted from the document.
    """
    text = await text_extractor.extract_text(file)
    if not text:
        raise ValueError("The document contains no extractable text")

    entities = await entity_extractor.extract_entities(text)

    if pseudonymize:
        text, entities = pseudonymizer.mask(text, entities)

    return text, entities
