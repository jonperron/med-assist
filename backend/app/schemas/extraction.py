from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime


class EntityDetail(BaseModel):
    """Detailed information about an extracted entity."""

    text: str = Field(description="The extracted entity text")
    label: str = Field(description="The entity label/type from the NER model")
    score: float = Field(description="Confidence score (0-1)")
    start: Optional[int] = Field(
        default=None,
        description=(
            "Start position in the text. Absent when the document text was not "
            "retained, since an offset means nothing without the text."
        ),
    )
    end: Optional[int] = Field(
        default=None,
        description=(
            "End position in the text. Absent when the document text was not "
            "retained, since an offset means nothing without the text."
        ),
    )


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
    text: Optional[str] = Field(
        default=None,
        description=(
            "Extracted text from the document. Null unless the deployment "
            "opted into storing document text."
        ),
    )
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
    expires_in_seconds: Optional[int] = Field(
        default=None,
        description="Seconds before the stored document is automatically deleted",
    )


class AnalysisResponse(BaseModel):
    """Result of a stateless analysis. Nothing behind this response is stored."""

    text: str = Field(
        description=(
            "Text extracted from the submitted document, pseudonymised when "
            "requested. Returned to the caller and kept nowhere else."
        )
    )
    extracted_entities: ExtractedEntities = Field(
        description="Medical entities found in the text with detailed information"
    )
    mapping_info: Optional[Dict[str, str]] = Field(
        default=None,
        description="Information about the label mapping used (language, dataset)",
    )
    pseudonymized: bool = Field(
        description=(
            "Whether the masking pass ran. It reports that every identifier the "
            "model detected was replaced, not that no identifier remains: an "
            "identifier the model misses is an identifier that survives."
        )
    )
    retained: bool = Field(
        default=False,
        description="Always false: this endpoint never writes to storage",
    )

