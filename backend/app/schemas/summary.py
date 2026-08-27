from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class DateRange(BaseModel):
    """The stretch of time a batch of documents covers."""

    start: date = Field(description="The earliest document date in the batch")
    end: date = Field(
        description=(
            "The latest document date in the batch. Equal to `start` when only "
            "one document in the batch carries a date."
        )
    )


class Finding(BaseModel):
    """One deduplicated finding, and which documents it came from."""

    text: str = Field(description="The span the model marked, as it is reported")
    documents: List[int] = Field(
        description=(
            "Indices into the submitted batch, ascending, of every document "
            "this finding was found in. They index the request's own file "
            "order - and `AnalysisResponse.documents` - so a caller can name "
            "the source from what it submitted, without this path ever having "
            "to echo a filename."
        )
    )


class SummarySection(BaseModel):
    """One clinical axis of the summary, as a heading and its findings."""

    key: str = Field(description="Stable category key, e.g. 'pathologies'")
    heading: str = Field(description="Human-readable heading for the section")
    sentence: str = Field(
        description="The section's findings as one sentence, ready to read"
    )
    findings: List[Finding] = Field(
        description=(
            "The same findings as a list, most-supported first, for a caller "
            "that would rather lay them out itself"
        )
    )


class ClinicalSummary(BaseModel):
    """
    A readable summary of one or more documents about the same patient.

    Everything here is assembled from what the NER model emitted. No wording is
    generated: each finding is a span the model marked, deduplicated across the
    submitted documents and placed under a fixed heading.
    """

    patient: Optional[str] = Field(
        default=None,
        description=(
            "The demographic line, e.g. 'Patient, 67 ans, homme.' Absent when "
            "the documents carry no demographic mention."
        ),
    )
    sections: List[SummarySection] = Field(
        default=[],
        description="Clinical sections, in reading order. Empty ones are omitted.",
    )
    # Required and nullable rather than defaulted, like
    # `AnalyzedDocument.document_date` which it is read beside: an optional
    # field generates an optional type, and a client testing it for falsity
    # would then read an absent value and a batch nothing could be dated as the
    # same thing.
    date_range: Optional[DateRange] = Field(
        description=(
            "The stretch of time the dated documents cover, for a caller "
            "placing the summary in time. Absent when no submitted document "
            "carries a date this could be sure of - which is common, and not "
            "an error. Only documents that were read can be dated: see "
            "`AnalysisResponse.documents[].document_date` for the date behind "
            "each end of the range."
        ),
    )
    document_count: int = Field(
        description=(
            "How many documents were read to build this summary. Lower than "
            "the number submitted when a document could not be read: see "
            "`AnalysisResponse.documents[].read`."
        )
    )
    empty: bool = Field(
        default=False,
        description=(
            "True when nothing clinical was found. The caller should say so "
            "rather than render an empty page."
        ),
    )
