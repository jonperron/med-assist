from typing import List, Union
from uuid import uuid4

from fastapi import APIRouter, HTTPException, File, UploadFile

from app.schemas.upload import (
    FileValidationError,
    MultipleUploadResponse,
    UploadResponse,
    UploadErrorResponse,
)
from app.use_cases.save_file import save_batch, save_file
from app.use_cases.validate_file import validate_upload_file

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
        HTTPException: 400 for invalid file type, 500 for server errors
    """
    # Validate file type
    await validate_upload_file(file)

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


@router.post(
    "/upload_documents/",
    response_model=Union[
        MultipleUploadResponse, UploadErrorResponse, FileValidationError
    ],
    responses={
        200: {
            "model": MultipleUploadResponse,
            "description": "File uploaded successfully",
        },
        400: {
            "model": FileValidationError,
            "description": "Invalid file type or format",
        },
        500: {"model": UploadErrorResponse, "description": "Internal server error"},
    },
)
async def upload_documents(
    files: List[UploadFile] = File(
        ...,
        description="List of medical documents to upload. Supported formats: PDF, DOC, DOCX, TXT. Maximum size: 10MB per file.",
    ),
) -> MultipleUploadResponse:
    """
    Upload multiple medical documents for text extraction and entity recognition.

    Args:
        file: The uploaded file (PDF, DOC, DOCX, TXT)

    Returns:
        MultipleUploadResponse: Contains batch id with associated file ids

    Raises:
        HTTPException: 400 for invalid file type, 500 for server errors
    """
    batch_id = uuid4()
    file_ids = []

    for file in files:
        await validate_upload_file(file)

        try:
            file_id = uuid4()
            success = await save_file(file_id, file)

            if not success:
                raise HTTPException(
                    status_code=500,
                    detail={"message": "Failed to save file"},
                )

            file_ids.append(str(file_id))

        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail={"message": "Internal server error", "error_code": str(e)},
            )

    await save_batch(batch_id, file_ids)
    return MultipleUploadResponse(
        batch_id=str(batch_id),
        files_ids=file_ids,
        message="Files uploaded successfully.",
    )
