from typing import Union

from fastapi import APIRouter, HTTPException, Path

from app.use_cases.extract_entities import extract_entities
from app.schemas.extraction import ExtractionResponse, ErrorResponse, ExtractedEntities

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
) -> Union[ExtractionResponse, ErrorResponse]:
    """
    Endpoint to retrieve extracted text and entities from a processed file.

    Args:
        file_id: The unique identifier of the file to extract text from

    Returns:
        ExtractionResponse: Contains the file ID, extracted text, and identified medical entities

    Raises:
        HTTPException: 404 if file not found or not processed yet
    """
    extracted_text = await extract_entities(file_id)

    if not extracted_text:
        raise HTTPException(
            status_code=404, detail={"message": "File not found or not processed yet."}
        )

    return ExtractionResponse(
        file_id=file_id,
        text=extracted_text,
        extracted_entities=ExtractedEntities(diseases=[], symptoms=[], treatments=[]),
    )
