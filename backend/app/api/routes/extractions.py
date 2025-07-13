from app.use_cases.extract_entities import extract_entities
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/get_extracted_text/{file_id}")
async def get_extracted_text(
    file_id: str,
):
    """
    Endpoint to retrieve extracted text.
    """
    extracted_text = await extract_entities(file_id)

    if not extracted_text:
        return JSONResponse(
            status_code=404, content={"message": "File not found or not processed yet."}
        )

    return JSONResponse(
        status_code=200,
        content={
            "file_id": file_id,
            "text": extracted_text,
            "extracted_entities": {
                "diseases": [],
                "symptoms": [],
                "treatments": [],
            },  # Placeholder
        },
    )
