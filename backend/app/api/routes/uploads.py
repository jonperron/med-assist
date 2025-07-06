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
    file_id = file.filename

    # Extract and store
    file_handler = FileHandler(redis_storage=redis_storage)
    await file_handler.extract_text(file)

    return JSONResponse(
        status_code=200,
        content={
            "message": f"File '{file.filename}' uploaded successfully. Extraction pending.",
            "file_id": file_id,
        },
    )
