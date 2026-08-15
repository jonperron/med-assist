from uuid import UUID

from fastapi import APIRouter, HTTPException, Path, Depends

from app.schemas.errors import ErrorResponse
from app.schemas.extraction import ExtractedEntities, ExtractionResponse
from app.interfaces.repositories_interfaces import TextRepositoryInterface
from app.interfaces.service_interfaces import EntityExtractionServiceInterface
from app.core.dependencies import get_text_repository, get_entity_extractor
from app.core.validation import parse_file_id

router = APIRouter()


@router.get(
    "/get_extracted_text/{file_id}",
    response_model=ExtractionResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file ID format"},
        404: {
            "model": ErrorResponse,
            "description": "File not found or not processed yet",
        },
    },
)
async def get_extracted_text(
    file_id: str = Path(
        ...,
        description=("Unique identifier of the uploaded file to read entities from"),
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    ),
    text_repository: TextRepositoryInterface = Depends(get_text_repository),
    entity_extractor: EntityExtractionServiceInterface = Depends(get_entity_extractor),
) -> ExtractionResponse:
    """
    Endpoint to retrieve the entities extracted from a processed file.

    Entities are extracted at upload time, so this only reads what was stored.
    The document text comes back only when the deployment kept it.

    Args:
        file_id: The unique identifier of the file to read
        text_repository: Injected text repository dependency
        entity_extractor: Injected entity extractor dependency

    Returns:
        ExtractionResponse: Contains the file ID, identified medical entities and,
        when retained, the extracted text

    Raises:
        HTTPException: 404 if file not found or not processed yet
    """
    file_uuid: UUID = parse_file_id(file_id)

    extracted_entities = await text_repository.get_entities(file_uuid)

    if extracted_entities is None:
        raise HTTPException(
            status_code=404, detail={"message": "File not found or not processed yet."}
        )

    return ExtractionResponse(
        file_id=file_id,
        text=await text_repository.get_text(file_uuid),
        extracted_entities=ExtractedEntities(**extracted_entities),
        mapping_info=entity_extractor.get_mapping_info(),
        expires_in_seconds=await text_repository.get_document_ttl(file_uuid),
    )
