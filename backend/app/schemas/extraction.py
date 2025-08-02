from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class ExtractedEntities(BaseModel):
    diseases: List[str] = Field(description="List of identified diseases")
    symptoms: List[str] = Field(description="List of identified symptoms")
    treatments: List[str] = Field(description="List of identified treatments")


class ExtractionResponse(BaseModel):
    file_id: str = Field(description="Unique identifier of the processed file")
    text: str = Field(description="Extracted text from the document")
    extracted_entities: ExtractedEntities = Field(
        description="Medical entities found in the text"
    )
    processed_at: Optional[datetime] = Field(
        default=None, description="When the extraction was completed"
    )
    confidence_scores: Optional[dict] = Field(
        default=None, description="Confidence scores for extracted entities"
    )


class ErrorResponse(BaseModel):
    message: str = Field(description="Error message")
    error_code: Optional[str] = Field(default=None, description="Specific error code")
    file_id: Optional[str] = Field(default=None, description="File ID if applicable")
