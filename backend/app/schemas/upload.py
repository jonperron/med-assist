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


class MultipleUploadResponse(BaseModel):
    batch_id: str = Field(description="Unique identifier of the batch")
    file_ids: List[str] = Field(description="List of file IDs in the batch")
    message: str = Field(description="Batch upload status message")
    total_files: Optional[int] = Field(
        default=None, description="Total number of files processed"
    )
    uploaded_at: Optional[datetime] = Field(
        default=None, description="Upload timestamp"
    )


class UploadErrorResponse(BaseModel):
    message: str = Field(description="Error message")
    error_code: Optional[str] = Field(default=None, description="Specific error code")
    file_name: Optional[str] = Field(
        default=None, description="Name of the problematic file"
    )


class FileValidationError(BaseModel):
    message: str = Field(description="Validation error message")
    allowed_types: List[str] = Field(description="List of allowed file types")
    received_type: str = Field(
        description="The received file type that failed validation"
    )
    field_name: Optional[str] = Field(
        default=None, description="Name of the field that failed validation"
    )
