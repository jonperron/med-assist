from typing import Union
from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Depends

from app.use_cases.extract_entities import extract_entities
from app.schemas.extraction import ExtractionResponse, ErrorResponse, ExtractedEntities
from app.repositories.text_repository import TextRepositoryInterface
from app.services.entity_extractor import EntityExtractor
from app.core.dependencies import get_text_repository, get_entity_extractor

router = APIRouter()


@router.get(
    "/get_extracted_text/{file_id}",
    response_model=Union[ExtractionResponse, ErrorResponse],
    responses={
        200: {
            "model": ExtractionResponse,
            "description": "Successfully extracted text and entities",
        },
        404: {
            "model": ErrorResponse,
            "description": "File not found or not processed yet",
        },
    },
)
async def get_extracted_text(
    file_id: str = Path(
        ...,
        description="Unique identifier of the uploaded file to extract text and entities from",
        example="123e4567-e89b-12d3-a456-426614174000",
    ),
    text_repository: TextRepositoryInterface = Depends(get_text_repository),
    entity_extractor: EntityExtractor = Depends(get_entity_extractor),
) -> Union[ExtractionResponse, ErrorResponse]:
    """
    Endpoint to retrieve extracted text and entities from a processed file.

    Args:
        file_id: The unique identifier of the file to extract text from
        text_repository: Injected text repository dependency
        entity_extractor: Injected entity extractor dependency

    Returns:
        ExtractionResponse: Contains the file ID, extracted text, and identified medical entities

    Raises:
        HTTPException: 404 if file not found or not processed yet
    """
    # Convert file_id to UUID
    try:
        file_uuid: UUID = UUID(file_id)
    except ValueError as exc:
        # If file_id is not a valid UUID, create a deterministic approach
        # For now, we'll raise an error since we expect valid UUIDs
        raise HTTPException(
            status_code=400,
            detail={"message": "Invalid file ID format. Expected UUID."},
        ) from exc

    extracted_entities = await extract_entities(
        file_uuid, text_repository, entity_extractor
    )

    if not extracted_entities:
        raise HTTPException(
            status_code=404, detail={"message": "File not found or not processed yet."}
        )

    # Get the text for the response
    text = await text_repository.get_text(file_uuid)

    return ExtractionResponse(
        file_id=file_id,
        text=text or "",
        extracted_entities=ExtractedEntities(**extracted_entities),
        mapping_info=entity_extractor.get_mapping_info(),
    )
