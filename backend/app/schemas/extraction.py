from enum import Enum

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime

from app.schemas.summary import ClinicalSummary


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


class UnreadableReason(str, Enum):
    """
    Why a submitted document is not behind the summary.

    Closed on purpose, and content-free: a caller renders the position it
    submitted, never a filename or a parser message. More members may be added
    as more ways to fail are told apart; today every failure a document can
    cause on this path is "nothing could be read from it".
    """

    NO_TEXT = "no_text"


class AnalyzedDocument(ExtractedEntities):
    """
    One submitted document: its entities, and whether it was read at all.

    Callers that already read `documents[i]` as entities keep working - the
    entity categories are unchanged, and an unread document simply has none.
    The document is identified by its position in the list, which is the
    caller's own submission order, so no filename has to cross the boundary for
    the caller to say which of its files was skipped.
    """

    # Both are required rather than defaulted: an optional field generates an
    # optional type, and a client testing `read` for falsity would then read an
    # absent value as a document that failed.
    read: bool = Field(
        description=(
            "False when no text could be read from this document. It is then "
            "not behind the summary, and its entity categories are empty."
        ),
    )
    unreadable_reason: Optional[UnreadableReason] = Field(
        description="Why the document could not be read. Null when it was read.",
    )


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

    summary: ClinicalSummary = Field(
        description=(
            "The submitted documents merged into one readable patient summary. "
            "This is what the endpoint is for; the rest is detail behind it."
        )
    )
    documents: List[AnalyzedDocument] = Field(
        description=(
            "Every submitted document, in submission order: the entities found "
            "in it for a caller that needs more than the summary, and whether "
            "it could be read at all. A document with `read` false is not "
            "behind the summary - the batch is refused outright only when none "
            "of them could be read."
        )
    )
    mapping_info: Optional[Dict[str, str]] = Field(
        default=None,
        description="Information about the label mapping used (language, dataset)",
    )
    retained: bool = Field(
        default=False,
        description="Always false: this endpoint never writes to storage",
    )
