from app.core.dependencies import get_redis_storage
from app.db.redis import RedisStorage
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/get_extracted_text/{file_id}")
async def get_extracted_text(
    file_id: str,
    redis_storage: RedisStorage = Depends(get_redis_storage),
):
    """
    Endpoint to retrieve extracted text.
    """
    extracted_text = await redis_storage.get_value(file_id)

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
