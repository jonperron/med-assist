from uuid import UUID

from typing import Optional, Dict, List
from fastapi import Depends

from app.repositories.text_repository import TextRepositoryInterface
from app.services.entity_extractor import EntityExtractor
from app.core.dependencies import get_text_repository, get_entity_extractor


async def extract_entities(
    file_id: UUID,
    text_repository: TextRepositoryInterface = Depends(get_text_repository),
    entity_extractor: EntityExtractor = Depends(get_entity_extractor),
) -> Optional[Dict[str, List[str]]]:
    """
    Extract entities from text associated with a file ID.

    :param file_id: The unique identifier for the file.
    :param text_repository: Injected text repository service.
    :param entity_extractor: Injected entity extraction service.
    :return: Extracted entities or None if text not found.
    """
    text = await text_repository.get_text(file_id)
    return entity_extractor.extract_entities(text) if text else None
