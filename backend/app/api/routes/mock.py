from typing import Dict, List

from fastapi import APIRouter, Path, Query

from app.core.validation import parse_file_id
from app.schemas.extraction import (
    EntityDetail,
    ExtractedEntities,
    ExtractionResponse,
)
from app.services.file_handler import drop_offsets

mock_router = APIRouter()

# A mock is only worth having if it answers the shape the real API answers, so
# it is built from the same models with the offsets the text really has.
MOCK_TEXT = (
    "Le patient présente une fièvre et a été traité avec du paracétamol "
    "pour la grippe."
)

MOCK_ENTITIES: Dict[str, List[EntityDetail]] = {
    "symptoms": [
        EntityDetail(text="fièvre", label="sosy", score=0.98, start=24, end=30)
    ],
    "treatments": [
        EntityDetail(
            text="paracétamol", label="substance", score=0.96, start=55, end=66
        )
    ],
    "pathologies": [
        EntityDetail(text="grippe", label="pathologie", score=0.94, start=75, end=81)
    ],
}


@mock_router.get(
    "/mock_extracted_text/{file_id}",
    response_model=ExtractionResponse,
    responses={
        200: {
            "model": ExtractionResponse,
            "description": "Mocked extracted text and entities (dev only)",
        }
    },
    tags=["dev", "mock"],
)
async def mock_extracted_text(
    file_id: str = Path(
        ...,
        description="Unique identifier for the mock extracted text",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    ),
    retained: bool = Query(
        default=False,
        description=(
            "Answer as a deployment that kept the document text "
            "(STORE_DOCUMENT_TEXT=true). Off by default, like the deployment."
        ),
    ),
) -> ExtractionResponse:
    """
    Mock endpoint for frontend development.

    Returns a dummy ExtractionResponse payload. Nothing here is read from
    storage and no model runs, but the id is validated and the default answer
    is the one the shipped configuration gives: no text, and no offsets, since
    an offset means nothing without the text it indexes.
    """
    entities = MOCK_ENTITIES if retained else drop_offsets(MOCK_ENTITIES)

    return ExtractionResponse(
        file_id=str(parse_file_id(file_id)),
        text=MOCK_TEXT if retained else None,
        extracted_entities=ExtractedEntities(**entities),
        mapping_info={"language": "fr", "dataset": "french_clinical"},
        expires_in_seconds=3600,
    )
