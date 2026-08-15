from fastapi import APIRouter, Path

from app.schemas.extraction import (
    EntityDetail,
    ExtractedEntities,
    ExtractionResponse,
)

mock_router = APIRouter()

# A mock is only worth having if it answers the shape the real API answers, so
# it is built from the same models with the offsets the text really has.
MOCK_TEXT = (
    "Le patient présente une fièvre et a été traité avec du paracétamol "
    "pour la grippe."
)


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
) -> ExtractionResponse:
    """
    Mock endpoint for frontend development.

    Returns a dummy ExtractionResponse payload. Nothing here is read from
    storage and no model runs.
    """
    return ExtractionResponse(
        file_id=file_id,
        text=MOCK_TEXT,
        extracted_entities=ExtractedEntities(
            symptoms=[
                EntityDetail(text="fièvre", label="sosy", score=0.98, start=24, end=30)
            ],
            treatments=[
                EntityDetail(
                    text="paracétamol",
                    label="substance",
                    score=0.96,
                    start=55,
                    end=66,
                )
            ],
            pathologies=[
                EntityDetail(
                    text="grippe", label="pathologie", score=0.94, start=75, end=81
                )
            ],
        ),
        mapping_info={"language": "fr", "dataset": "french_clinical"},
        expires_in_seconds=3600,
    )
