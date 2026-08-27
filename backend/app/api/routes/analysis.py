import logging
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import ValidationError

from app.core.dependencies import (
    get_entity_extractor,
    get_text_extractor,
)
from app.core.readiness import require_the_model
from app.interfaces.service_interfaces import (
    EntityExtractionServiceInterface,
    TextExtractionServiceInterface,
)
from app.schemas.errors import UNREADABLE_DOCUMENT, ErrorResponse
from app.schemas.extraction import (
    AnalysisResponse,
    AnalyzedDocument,
    ExtractedEntities,
    UnreadableReason,
)
from app.use_cases.analyze_document import (
    ReadDocument,
    UnreadableDocument,
    summarize_documents,
)
from app.use_cases.validate_file import validate_batch

router = APIRouter()
logger = logging.getLogger(__name__)


# The entity categories, taken from the schema so the two cannot drift.
ENTITY_CATEGORIES = tuple(ExtractedEntities.model_fields)


def describe(document: ReadDocument) -> AnalyzedDocument:
    """Report one submitted document, read or not, at its submitted position."""
    if document.entities is None:
        return AnalyzedDocument(
            read=False,
            unreadable_reason=UnreadableReason.NO_TEXT,
            document_date=None,
        )

    # Only the known categories are spread. The keys come from the label
    # mapping, and one named `read` would otherwise be splatted over the read
    # status - a mapping deciding whether a document counts as readable.
    found = {
        category: document.entities[category]
        for category in ENTITY_CATEGORIES
        if category in document.entities
    }
    return AnalyzedDocument(
        **found,
        read=True,
        unreadable_reason=None,
        document_date=document.document_date,
    )


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    dependencies=[Depends(require_the_model)],
    responses={
        400: {"model": ErrorResponse, "description": "Invalid or unreadable document"},
        413: {
            "model": ErrorResponse,
            "description": "A file is too large, or the batch holds too many files",
        },
        500: {"model": ErrorResponse, "description": "Internal server error"},
        503: {"model": ErrorResponse, "description": "The model is not loaded yet"},
    },
)
async def analyze(
    files: List[UploadFile] = File(
        ...,
        description=(
            "The documents to summarise (PDF, DOCX, TXT). Several documents are "
            "taken to be about the same patient and merged into one summary."
        ),
    ),
    text_extractor: TextExtractionServiceInterface = Depends(get_text_extractor),
    entity_extractor: EntityExtractionServiceInterface = Depends(get_entity_extractor),
) -> AnalysisResponse:
    """
    Summarise one or more medical documents in a single request, storing nothing.

    The documents are read, analysed and answered in memory. No file id is
    issued because there is nothing to come back for, and nothing to delete
    later. The document text is not echoed back: the summary is the product,
    and returning the text would widen what leaves the server for no gain.

    A batch holding one document that cannot be read still answers 200, with
    that document marked unread and the summary built from the rest. Only a
    batch where nothing could be read is refused.

    Args:
        files: The uploaded documents (PDF, DOCX, TXT)

    Returns:
        AnalysisResponse: The merged summary and the entities behind it

    Raises:
        HTTPException: 400 for an invalid file or a batch nothing could be read
            from, 413 for a file or batch that is too large, 500 for server
            errors
    """
    await validate_batch(files)

    try:
        summary, documents = await summarize_documents(
            files=files,
            text_extractor=text_extractor,
            entity_extractor=entity_extractor,
        )
        # Built inside the guard: a malformed EntityDetail raises a pydantic
        # error that quotes the offending value, which would be document
        # content. A category the model emits that the schema lacks is not an
        # error - `describe` keeps the known ones, so it is dropped silently by
        # design.
        return AnalysisResponse(
            summary=summary,
            documents=[describe(document) for document in documents],
            mapping_info=entity_extractor.get_mapping_info(),
        )
    except ValidationError as exc:
        # A pydantic error quotes the value it rejected, so it is never
        # forwarded, and it is caught ahead of the generic handler below to be
        # logged as the shape problem it is rather than as an unknown failure.
        logger.error("Analysis produced an unexpected entity shape")
        raise HTTPException(
            status_code=500,
            detail={"message": "Internal server error"},
        ) from exc
    except UnreadableDocument as exc:
        # Nothing in the batch could be read, so there is no partial summary to
        # answer with. The message is fixed and carries no document content -
        # in particular it does not say which of the submitted files failed,
        # since that would be a filename. Which position failed is reported in
        # the 200 body instead, where there is a summary to qualify.
        raise HTTPException(
            status_code=400,
            detail={"message": UNREADABLE_DOCUMENT},
        ) from exc
    except Exception as exc:
        # Every other failure, a plain ValueError included, is the server's
        # problem rather than the caller's document, and answers the same way.
        logger.error("Analysis failed (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=500,
            detail={"message": "Internal server error"},
        ) from exc
