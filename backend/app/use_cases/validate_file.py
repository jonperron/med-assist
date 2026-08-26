import os
from typing import List

from fastapi import HTTPException, UploadFile

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024

# Each file is capped at MAX_FILE_SIZE_BYTES; this bounds how many of them a
# single request can queue behind a model that admits one document at a time.
# The size ceiling bounds bytes, not inference time, and twenty small text
# files are the expensive case - so a small deployment can lower this.
MAX_BATCH_FILES = int(os.getenv("MAX_BATCH_FILES", "20"))
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}


async def validate_upload_file(
    file: UploadFile,
) -> bool:
    # Enforce hard size limit before parsing to reduce memory/CPU abuse risk.
    current_pos = file.file.tell()
    file.file.seek(0, os.SEEK_END)
    file_size = file.file.tell()
    file.file.seek(current_pos)
    if file_size > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "message": "File too large",
                "max_size_bytes": MAX_FILE_SIZE_BYTES,
                "received_size_bytes": file_size,
            },
        )

    # Check content type
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid file type",
                "allowed_types": ["PDF", "DOCX", "TXT"],
                "received_type": file.content_type,
            },
        )

    # Check extension
    if file.filename is None:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "No filename provided",
                "allowed_extensions": list(ALLOWED_EXTENSIONS),
            },
        )

    _, ext = os.path.splitext(file.filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        # The extension is not echoed back: it is a slice of the filename, and
        # a document named "compte-rendu-Jeanne.Dupont" has a patient's name
        # where an extension should be.
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid file extension",
                "allowed_extensions": list(ALLOWED_EXTENSIONS),
            },
        )
    return True


async def validate_batch(files: List[UploadFile]) -> None:
    """
    Refuse a batch before any of it is processed.

    The whole batch is validated up front so a refusal on the fourth file
    cannot leave the first three already analysed - or, on the storing path,
    already written under ids the caller never receives.

    :param files: The uploaded files.
    :raises HTTPException: 400 for an empty batch or a rejected file, 413 for a
        file that is too large or a batch that holds too many.
    """
    if not files:
        raise HTTPException(
            status_code=400,
            detail={"message": "No file was submitted"},
        )

    if len(files) > MAX_BATCH_FILES:
        raise HTTPException(
            status_code=413,
            detail={
                "message": "Too many files in one batch",
                "max_files": MAX_BATCH_FILES,
            },
        )

    for file in files:
        await validate_upload_file(file)
