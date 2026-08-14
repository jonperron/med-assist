import logging
from typing import List, Union
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Path,
    UploadFile,
    status,
)

from app.schemas.upload import (
    FileValidationError,
    MultipleUploadResponse,
    UploadResponse,
    UploadErrorResponse,
)
from app.use_cases.save_file import save_batch, save_file
from app.use_cases.validate_file import validate_upload_file
from app.interfaces.repositories_interfaces import TextRepositoryInterface
from app.services.file_handler import FileHandler
from app.core.dependencies import get_file_handler, get_text_repository
from app.core.validation import parse_file_id

router = APIRouter()
logger = logging.getLogger(__name__)

# Each file is capped at 10 MB by validate_upload_file; this bounds how many of
# them a single request can queue behind the model.
MAX_BATCH_FILES = 20


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
    file: UploadFile = File(..., description="The file to upload (PDF, DOCX, TXT)."),
    pseudonymize: bool | None = Form(
        default=None,
        description=(
            "Mask entities detected as patient information. Defaults to the "
            "deployment's PSEUDONYMIZE_ENTITIES setting."
        ),
    ),
    file_handler: FileHandler = Depends(get_file_handler),
    text_repository: TextRepositoryInterface = Depends(get_text_repository),
):
    """
    Upload a medical document for text extraction and entity recognition.

    Args:
        file: The uploaded file (PDF, DOCX, TXT)
        pseudonymize: Whether to mask detected patient identifiers

    Returns:
        UploadResponse: Contains file ID, filename, and upload confirmation

    Raises:
        HTTPException: 400 for invalid file type, 500 for server errors
    """
    # Validate file type
    await validate_upload_file(file)

    file_id = uuid4()

    try:
        success = await save_file(file_id, file, file_handler, pseudonymize)

        if not success:
            raise HTTPException(
                status_code=500,
                detail={"message": "Failed to save file"},
            )

        return UploadResponse(
            file_id=str(file_id),
            filename=file.filename or "unknown",
            message="File uploaded and analysed successfully.",
            expires_in_seconds=await text_repository.get_document_ttl(file_id),
        )
    except HTTPException:
        raise
    except Exception as e:
        # The file id is the only identifier that may be logged: clinical
        # filenames routinely carry patient names, and a traceback or an
        # exception message can quote document content.
        logger.error(
            "Unexpected error while uploading document %s (%s)",
            file_id,
            type(e).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail={"message": "Internal server error"},
        ) from e


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
        description=(
            "List of medical documents to upload. Supported formats: "
            "PDF, DOCX, TXT. Maximum size: 10MB per file."
        ),
    ),
    pseudonymize: bool | None = Form(
        default=None,
        description=(
            "Mask entities detected as patient information. Defaults to the "
            "deployment's PSEUDONYMIZE_ENTITIES setting."
        ),
    ),
    file_handler: FileHandler = Depends(get_file_handler),
) -> MultipleUploadResponse:
    """
    Upload multiple medical documents for text extraction and entity recognition.

    Args:
        files: The uploaded files (PDF, DOCX, TXT)
        pseudonymize: Whether to mask detected patient identifiers

    Returns:
        MultipleUploadResponse: Contains batch id with associated file ids

    Raises:
        HTTPException: 400 for invalid file type, 500 for server errors
    """
    if len(files) > MAX_BATCH_FILES:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail={
                "message": "Too many files in one batch",
                "max_files": MAX_BATCH_FILES,
            },
        )

    batch_id = uuid4()
    file_ids = []

    for file in files:
        await validate_upload_file(file)
        file_id = uuid4()

        try:
            success = await save_file(file_id, file, file_handler, pseudonymize)

            if not success:
                raise HTTPException(
                    status_code=500,
                    detail={"message": "Failed to save file"},
                )

            file_ids.append(str(file_id))

        except HTTPException:
            raise
        except Exception as e:
            # See upload_document: never log the filename or the exception text.
            logger.error(
                "Unexpected error while uploading document %s in batch %s (%s)",
                file_id,
                batch_id,
                type(e).__name__,
            )
            raise HTTPException(
                status_code=500,
                detail={"message": "Internal server error"},
            ) from e

    await save_batch(batch_id, file_ids, file_handler)
    return MultipleUploadResponse(
        batch_id=str(batch_id),
        file_ids=file_ids,
        message="Files uploaded successfully.",
    )


@router.delete(
    "/documents/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Document deleted"},
        400: {"model": UploadErrorResponse, "description": "Invalid file ID format"},
        404: {"model": UploadErrorResponse, "description": "Document not found"},
    },
)
async def delete_document(
    file_id: str = Path(
        ...,
        description="Unique identifier of the document to delete",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    ),
    text_repository: TextRepositoryInterface = Depends(get_text_repository),
) -> None:
    """
    Delete a stored document before its retention window expires.

    Args:
        file_id: The unique identifier of the document to delete
        text_repository: Injected text repository dependency

    Raises:
        HTTPException: 400 for a malformed file ID, 404 if nothing was stored
    """
    if not await text_repository.delete_document(parse_file_id(file_id)):
        raise HTTPException(
            status_code=404,
            detail={"message": "Document not found or already expired."},
        )
