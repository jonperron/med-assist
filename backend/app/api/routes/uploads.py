import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, List
from uuid import UUID, uuid4

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

from app.schemas.errors import UNREADABLE_DOCUMENT, ErrorResponse
from app.schemas.upload import MultipleUploadResponse, UploadResponse
from app.use_cases.validate_file import validate_upload_file
from app.interfaces.repositories_interfaces import TextRepositoryInterface
from app.services.file_handler import FileHandler
from app.core.dependencies import get_file_handler, get_text_repository
from app.core.readiness import require_the_model
from app.core.validation import parse_file_id

router = APIRouter()
logger = logging.getLogger(__name__)

# Each file is capped at 10 MB by validate_upload_file; this bounds how many of
# them a single request can queue behind the model.
MAX_BATCH_FILES = 20


@asynccontextmanager
async def failures_stay_generic(file_id: UUID) -> AsyncIterator[None]:
    """
    Turn any unexpected failure into a fixed 500, logged by file id alone.

    Clinical filenames routinely carry patient names, and a traceback or an
    exception message can quote document content, so neither reaches the log
    or the caller. Refusals raised on purpose pass through untouched.
    """
    try:
        yield
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(
            "Unexpected error while uploading document %s (%s)",
            file_id,
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=500,
            detail={"message": "Internal server error"},
        ) from exc


async def store_document(
    file: UploadFile,
    file_handler: FileHandler,
    pseudonymize: bool | None,
) -> UUID:
    """
    Validate one document, analyse it and persist what the deployment allows.

    A single upload is a batch of one, so both routes come through here and
    cannot drift apart in how they refuse a file.

    :param file: The uploaded file.
    :param file_handler: The service extracting and storing the document.
    :param pseudonymize: Ask for masking even when the deployment default is off.
    :return: The id the document was stored under.
    :raises HTTPException: 400/413 for a rejected file, 500 when storing fails.
    """
    await validate_upload_file(file)

    file_id = uuid4()
    async with failures_stay_generic(file_id):
        try:
            stored = await file_handler.process_file(file_id, file, pseudonymize)
        except ValueError as exc:
            # A document of a supported type that cannot be parsed is the
            # caller's problem, not a server fault - and /api/analyze already
            # answers 400 for the same file. The message is fixed upstream and
            # quotes nothing from the document.
            raise HTTPException(
                status_code=400,
                detail={"message": UNREADABLE_DOCUMENT},
            ) from exc

        if not stored:
            # process_file answers False for a document with no extractable
            # text: same cause, same answer.
            raise HTTPException(
                status_code=400,
                detail={"message": UNREADABLE_DOCUMENT},
            )

    return file_id


@router.post(
    "/upload_document/",
    response_model=UploadResponse,
    dependencies=[Depends(require_the_model)],
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Invalid file type, or a document that cannot be read",
        },
        413: {"model": ErrorResponse, "description": "File too large"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
        503: {"model": ErrorResponse, "description": "The model is not loaded yet"},
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
) -> UploadResponse:
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
    file_id = await store_document(file, file_handler, pseudonymize)

    async with failures_stay_generic(file_id):
        return UploadResponse(
            file_id=str(file_id),
            filename=file.filename or "unknown",
            message="File uploaded and analysed successfully.",
            expires_in_seconds=await text_repository.get_document_ttl(file_id),
        )


@router.post(
    "/upload_documents/",
    response_model=MultipleUploadResponse,
    dependencies=[Depends(require_the_model)],
    responses={
        400: {
            "model": ErrorResponse,
            "description": "Invalid file type, or a document that cannot be read",
        },
        413: {
            "model": ErrorResponse,
            "description": "A file is too large, or the batch holds too many files",
        },
        500: {"model": ErrorResponse, "description": "Internal server error"},
        503: {"model": ErrorResponse, "description": "The model is not loaded yet"},
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

    Each file is processed on its own and answered with its own id. The batch id
    only correlates the files of this request: nothing is written under it, so
    there is one less patient-adjacent key living out a retention window.

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

    # Validate the whole batch before storing any of it. A refusal on the
    # fourth file used to leave the first three in Redis under ids the client
    # never receives in the error response, so nobody could delete them before
    # the retention window closed.
    for file in files:
        await validate_upload_file(file)

    file_ids = [
        str(await store_document(file, file_handler, pseudonymize)) for file in files
    ]

    return MultipleUploadResponse(
        batch_id=str(uuid4()),
        file_ids=file_ids,
        message="Files uploaded successfully.",
    )


@router.delete(
    "/documents/{file_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {"description": "Document deleted"},
        400: {"model": ErrorResponse, "description": "Invalid file ID format"},
        404: {"model": ErrorResponse, "description": "Document not found"},
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
