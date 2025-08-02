from uuid import uuid4

from app.use_cases.save_file import save_file
from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/upload_document/")
async def upload_document(
    file: UploadFile = File(...),
):
    """
    Endpoint to upload a document.
    For now, it just saves the file name and type.
    Later, this will extract text.
    """
    file_id = uuid4()
    success = await save_file(file_id, file)

    if not success:
        return JSONResponse(
            status_code=400,
            content={"message": "Failed to extract text from the document."},
        )

    return JSONResponse(
        status_code=200,
        content={
            "message": f"File '{file.filename}' uploaded successfully. Extraction pending.",
            "file_id": str(file_id),
        },
    )
