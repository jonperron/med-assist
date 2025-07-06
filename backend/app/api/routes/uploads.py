from fastapi import APIRouter, UploadFile, File
from fastapi.responses import JSONResponse

from app.db.temp_store import extracted_data_store

router = APIRouter()

@router.post("/upload_document/")
async def upload_document(file: UploadFile = File(...)):
    """
    Endpoint to upload a document.
    For now, it just saves the file name and type.
    Later, this will extract text.
    """
    file_id = file.filename 
    extracted_data_store[file_id] = {
        "filename": file.filename,
        "content_type": file.content_type,
        "status": "uploaded, text extraction pending"
    }
    
    return JSONResponse(
        status_code=200,
        content={
            "message": f"File '{file.filename}' uploaded successfully. Extraction pending.",
            "file_id": file_id
        }
    )
