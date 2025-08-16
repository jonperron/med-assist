from fastapi import APIRouter, Path
from app.schemas.extraction import ExtractionResponse, ExtractedEntities

mock_router = APIRouter()


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
        example="dummy-uuid-1234",
    ),
) -> ExtractionResponse:
    """
    Mock endpoint for frontend development.
    Returns a dummy ExtractionResponse payload.
    """
    return ExtractionResponse(
        file_id=file_id,
        text="Le patient présente une fièvre et a été traité avec du paracétamol pour la grippe.",
        extracted_entities=ExtractedEntities(
            diseases=["grippe"], symptoms=["fièvre"], treatments=["paracétamol"]
        ),
    )
