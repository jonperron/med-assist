from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime


class EntityDetail(BaseModel):
    """Detailed information about an extracted entity."""

    text: str = Field(description="The extracted entity text")
    label: str = Field(description="The entity label/type from the NER model")
    score: float = Field(description="Confidence score (0-1)")
    start: int = Field(description="Start position in the text")
    end: int = Field(description="End position in the text")


class ExtractedEntities(BaseModel):
    """All extracted medical entities grouped by category."""

    patient_info: List[EntityDetail] = Field(
        default=[], description="Patient demographic information"
    )
    anatomy: List[EntityDetail] = Field(default=[], description="Anatomical structures")
    symptoms: List[EntityDetail] = Field(default=[], description="Signs and symptoms")
    examinations: List[EntityDetail] = Field(
        default=[], description="Medical examinations"
    )
    treatments: List[EntityDetail] = Field(
        default=[], description="Treatments and medications"
    )
    pathologies: List[EntityDetail] = Field(
        default=[], description="Diseases and conditions"
    )
    temporal: List[EntityDetail] = Field(default=[], description="Temporal information")
    measurements: List[EntityDetail] = Field(
        default=[], description="Measurements and values"
    )
    other: List[EntityDetail] = Field(default=[], description="Other medical entities")


class ExtractionResponse(BaseModel):
    file_id: str = Field(description="Unique identifier of the processed file")
    text: str = Field(description="Extracted text from the document")
    extracted_entities: ExtractedEntities = Field(
        description="Medical entities found in the text with detailed information"
    )
    processed_at: Optional[datetime] = Field(
        default=None, description="When the extraction was completed"
    )
    mapping_info: Optional[Dict[str, str]] = Field(
        default=None,
        description="Information about the label mapping used (language, dataset)",
    )


class ErrorResponse(BaseModel):
    message: str = Field(description="Error message")
    error_code: Optional[str] = Field(default=None, description="Specific error code")
    file_id: Optional[str] = Field(default=None, description="File ID if applicable")
