from uuid import uuid4

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import JSONResponse

from app.core.dependencies import get_redis_storage
from app.db.redis import RedisStorage
from app.use_cases.file_handler import FileHandler

router = APIRouter()


@router.post("/upload_document/")
async def upload_document(
    file: UploadFile = File(...),
    redis_storage: RedisStorage = Depends(get_redis_storage),
):
    """
    Endpoint to upload a document.
    For now, it just saves the file name and type.
    Later, this will extract text.
    """
    file_id = uuid4()
    # Extract and store
    file_handler = FileHandler(redis_storage=redis_storage)
    success = await file_handler.extract_text(file_id, file)

    if not success:
        return JSONResponse(
            status_code=400,
            content={"message": "Failed to extract text from the document."},
        )

    return JSONResponse(
        status_code=200,
        content={
            "message": f"File '{file.filename}' uploaded successfully. Extraction pending.",
            "file_id": file_id,
        },
    )
