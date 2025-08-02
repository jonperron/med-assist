from typing import Union
from uuid import uuid4

from fastapi import APIRouter, HTTPException, File, UploadFile

from app.schemas.upload import UploadResponse, UploadErrorResponse, FileValidationError
from app.use_cases.save_file import save_file

router = APIRouter()


@router.post(
    "/upload_document/",
    response_model=Union[UploadResponse, UploadErrorResponse, FileValidationError],
    responses={
        200: {"model": UploadResponse, "description": "File uploaded successfully"},
        400: {
            "model": FileValidationError,
            "description": "Invalid file type or format",
        },
        500: {"model": UploadErrorResponse, "description": "Internal server error"},
    },
)
async def upload_document(
    file: UploadFile = File(
        ..., description="The file to upload (PDF, DOC, DOCX, TXT)."
    ),
):
    """
    Upload a medical document for text extraction and entity recognition.

    Args:
        file: The uploaded file (PDF, DOC, DOCX, TXT)

    Returns:
        UploadResponse: Contains file ID, filename, and upload confirmation

    Raises:
        HTTPException: 400 for invalid file type, 413 for file too large, 500 for server errors
    """
    # Validate file type
    allowed_types = [
        "application/pdf",
        "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    ]

    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid file type",
                "allowed_types": ["PDF", "DOC", "DOCX", "TXT"],
                "received_type": file.content_type,
            },
        )

    try:
        file_id = uuid4()
        success = await save_file(file_id, file)

        if not success:
            raise HTTPException(
                status_code=500,
                detail={"message": "Failed to save file"},
            )

        return UploadResponse(
            file_id=str(file_id),
            filename=file.filename,
            message="File uploaded successfully. Extraction pending.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={"message": "Internal server error", "error_code": str(e)},
        )
