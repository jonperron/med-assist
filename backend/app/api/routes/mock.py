from datetime import date, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Path, Query

from app.core.validation import parse_file_id
from app.use_cases.validate_file import MAX_BATCH_FILES
from app.schemas.extraction import (
    AnalysisResponse,
    AnalyzedDocument,
    EntityDetail,
    ExtractedEntities,
    ExtractionResponse,
    UnreadableReason,
)
from app.services.file_handler import drop_offsets
from app.services.summarizer import summarize

mock_router = APIRouter()

# A mock is only worth having if it answers the shape the real API answers, so
# it is built from the same models with the offsets the text really has.
MOCK_TEXT = (
    "Le patient de 67 ans présente une fièvre et a été traité "
    "avec du paracétamol pour la grippe. Troponine I : 1,10 ng/mL."
)

MOCK_ENTITIES: Dict[str, List[EntityDetail]] = {
    "patient_info": [
        EntityDetail(text="67 ans", label="age", score=0.97, start=14, end=20),
    ],
    "symptoms": [
        EntityDetail(text="fièvre", label="sosy", score=0.98, start=34, end=40)
    ],
    "treatments": [
        EntityDetail(
            text="paracétamol", label="substance", score=0.96, start=65, end=76
        )
    ],
    "pathologies": [
        EntityDetail(text="grippe", label="pathologie", score=0.94, start=85, end=91)
    ],
    # An examination and the value that follows it, at the offsets the text
    # really has: the summarizer pairs them into one finding, and a mock that
    # left them apart would hide that from the client developing against it.
    "examinations": [
        EntityDetail(text="Troponine I", label="examen", score=0.93, start=93, end=104)
    ],
    "measurements": [
        EntityDetail(text="1,10 ng/mL", label="valeur", score=0.91, start=107, end=117)
    ],
}


# The dates the mock documents carry. They are stated rather than read out of
# MOCK_TEXT, which is one text shared by every mock document: dating them all
# from it would answer a batch with one date repeated, and the client would
# never see the range it has to render. A week apart, and old enough that they
# never drift into the future as the mock keeps being served.
MOCK_FIRST_DATE = date(2024, 3, 4)
MOCK_DATE_STEP = timedelta(days=7)


@mock_router.get(
    "/mock_extracted_text/{file_id}",
    response_model=ExtractionResponse,
    responses={
        200: {
            "model": ExtractionResponse,
            "description": "Mocked extracted text and entities (dev only)",
        }
    },
    tags=["dev", "mock"],
)
async def mock_extracted_text(
    file_id: str = Path(
        ...,
        description="Unique identifier for the mock extracted text",
        examples=["123e4567-e89b-12d3-a456-426614174000"],
    ),
    retained: bool = Query(
        default=False,
        description=(
            "Answer as a deployment that kept the document text "
            "(STORE_DOCUMENT_TEXT=true). Off by default, like the deployment."
        ),
    ),
) -> ExtractionResponse:
    """
    Mock endpoint for frontend development.

    Returns a dummy ExtractionResponse payload. Nothing here is read from
    storage and no model runs, but the id is validated and the default answer
    is the one the shipped configuration gives: no text, and no offsets, since
    an offset means nothing without the text it indexes.
    """
    entities = MOCK_ENTITIES if retained else drop_offsets(MOCK_ENTITIES)

    return ExtractionResponse(
        file_id=str(parse_file_id(file_id)),
        text=MOCK_TEXT if retained else None,
        extracted_entities=ExtractedEntities(**entities),
        mapping_info={"language": "fr", "dataset": "french_clinical"},
        expires_in_seconds=3600,
    )


@mock_router.get(
    "/mock_summary",
    response_model=AnalysisResponse,
    responses={
        200: {
            "model": AnalysisResponse,
            "description": "Mocked clinical summary (dev only)",
        }
    },
    tags=["dev", "mock"],
)
async def mock_summary(
    documents: int = Query(
        default=1,
        ge=1,
        le=MAX_BATCH_FILES,
        description="How many documents to pretend were submitted and merged.",
    ),
    unreadable: int = Query(
        default=0,
        ge=0,
        le=MAX_BATCH_FILES,
        description=(
            "How many of them to answer as unreadable, counting from the last. "
            "Capped at one below `documents`: a batch nothing could be read "
            "from is a 400 on the real route, not a summary."
        ),
    ),
) -> AnalysisResponse:
    """
    Mock endpoint for frontend development against the summary.

    No model runs, but the summary is built by the real `summarize`, so the
    shape and the merging rules are the ones the API actually applies - a mock
    that assembled the payload by hand would drift from them silently. That
    includes the partial answer: an unreadable document keeps its position and
    contributes nothing, exactly as it does on the real route.
    """
    skipped = min(unreadable, documents - 1)
    read = documents - skipped
    entities = [MOCK_ENTITIES] * read + [None] * skipped
    # An unread document carries no date, exactly as on the real route: there
    # is no text to have read one from.
    dates: List[Optional[date]] = [
        MOCK_FIRST_DATE + index * MOCK_DATE_STEP for index in range(read)
    ] + [None] * skipped

    return AnalysisResponse(
        summary=summarize(entities, dates),
        documents=[
            (
                AnalyzedDocument(
                    **document,
                    read=True,
                    unreadable_reason=None,
                    document_date=document_date,
                )
                if document is not None
                else AnalyzedDocument(
                    read=False,
                    unreadable_reason=UnreadableReason.NO_TEXT,
                    document_date=None,
                )
            )
            for document, document_date in zip(entities, dates)
        ],
        mapping_info={"language": "fr", "dataset": "french_clinical"},
    )
