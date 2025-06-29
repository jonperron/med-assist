from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse

from app.services.text_extractor import TextExtractor

router = APIRouter()

@router.post("/upload_document/")
async def upload_document(file: UploadFile = File(...)):
    """
    Endpoint to upload a document.
    For now, it just saves the file name and type.
    Later, this will extract text.
    """
    file_id = file.filename

    # Extract text from the document
    text_extractor = TextExtractor.extract_text(file)

    return JSONResponse(
        status_code=200,
        content={
            "message": f"File '{file.filename}' uploaded successfully. Extraction pending.",
            "file_id": file_id
        }
    )
