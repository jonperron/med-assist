import os

from fastapi import HTTPException, UploadFile

ALLOWED_EXTENSIONS = {".pdf", ".doc", ".docx", ".txt"}
ALLOWED_CONTENT_TYPES = {
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}


async def validate_upload_file(
    file: UploadFile,
) -> bool:
    # Check content type
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Invalid file type",
                "allowed_types": ["PDF", "DOC", "DOCX", "TXT"],
                "received_type": file.content_type,
            },
        )

    # Check extension
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
