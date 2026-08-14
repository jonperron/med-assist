from uuid import UUID

from typing import Optional, Dict, List

from app.interfaces.repositories_interfaces import TextRepositoryInterface
from app.schemas.extraction import EntityDetail


async def read_stored_entities(
    file_id: UUID,
    text_repository: TextRepositoryInterface,
) -> Optional[Dict[str, List[EntityDetail]]]:
    """
    Read the entities stored for a document.

    Entities are extracted once, when the document is uploaded, so reading a
    document never runs the model again and never needs its text.

    :param file_id: The unique identifier for the file.
    :param text_repository: The document repository.
    :return: Stored entities, or None when the document is gone.
    """
    return await text_repository.get_entities(file_id)
