from enum import Enum

from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import date

from app.schemas.summary import ClinicalSummary


class EntityDetail(BaseModel):
    """Detailed information about an extracted entity."""

    text: str = Field(description="The extracted entity text")
    label: str = Field(description="The entity label/type from the NER model")
    score: float = Field(description="Confidence score (0-1)")
    # The two offsets below index the text extracted from the document, and
    # that text never leaves the server - so an offset was unusable to a caller
    # and was, strictly, position information about clinical content crossing
    # the boundary for no gain. `exclude=True` keeps them off the wire and out
    # of the serialisation-mode schema FastAPI generates responses from, while
    # leaving them readable in Python: the summarizer pairs an examination with
    # the value that follows it by comparing them, and that runs before the
    # response is built.
    start: Optional[int] = Field(
        default=None,
        exclude=True,
        description=(
            "Internal only, never serialised: where the span starts in the "
            "text extracted from the document. The summarizer pairs spans by "
            "it; no response carries it."
        ),
    )
    end: Optional[int] = Field(
        default=None,
        exclude=True,
        description=(
            "Internal only, never serialised: where the span ends in the text "
            "extracted from the document. The summarizer pairs spans by it; no "
            "response carries it."
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
    document_date: Optional[date] = Field(
        description=(
            "The date this document carries, read from its head. Null when it "
            "carries none that could be established - a document with no date "
            "in its letterhead, or an unread one - which is common and not an "
            "error. It is the document's own date, not the file's timestamp "
            "and not a date mentioned inside the clinical text."
        ),
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
