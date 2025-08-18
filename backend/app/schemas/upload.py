from pydantic import BaseModel


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    message: str


class MultipleUploadResponse(BaseModel):
    batch_id: str
    file_ids: list[str]
    message: str


class UploadErrorResponse(BaseModel):
    message: str


class FileValidationError(BaseModel):
    message: str
    allowed_types: list[str]
    received_type: str
