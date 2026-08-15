from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class UploadResponse(BaseModel):
    file_id: str = Field(description="Unique identifier of the uploaded file")
    filename: str = Field(description="Original filename")
    message: str = Field(description="Upload status message")
    size: Optional[int] = Field(default=None, description="File size in bytes")
    content_type: Optional[str] = Field(
        default=None, description="MIME type of the file"
    )
    uploaded_at: Optional[datetime] = Field(
        default=None, description="Upload timestamp"
    )
    expires_in_seconds: Optional[int] = Field(
        default=None,
        description="Seconds before the stored document is automatically deleted",
    )


class MultipleUploadResponse(BaseModel):
    batch_id: str = Field(
        description=(
            "Identifier correlating the files of one upload request. Nothing is "
            "stored under it: the batch cannot be resolved server-side, only the "
            "file IDs can."
        )
    )
    file_ids: List[str] = Field(description="List of file IDs in the batch")
    message: str = Field(description="Batch upload status message")
    total_files: Optional[int] = Field(
        default=None, description="Total number of files processed"
    )
    uploaded_at: Optional[datetime] = Field(
        default=None, description="Upload timestamp"
    )

