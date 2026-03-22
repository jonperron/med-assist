import os

from fastapi import HTTPException, UploadFile

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024
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
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid file extension",
                "allowed_extensions": list(ALLOWED_EXTENSIONS),
                "received_extension": ext,
            },
        )
    return True
