import logging
from typing import AsyncIterator, List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.sse import EventSourceResponse
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
from app.schemas.progress import (
    AnalysisCompleted,
    AnalysisEvent,
    AnalysisFailed,
    BatchStarted,
    DocumentProgress,
    FailureReason,
)
from app.use_cases.analyze_document import (
    ReadDocument,
    UnreadableDocument,
    read_documents,
    summarize_documents,
    summarize_read_documents,
)
from app.use_cases.validate_file import validate_batch

router = APIRouter()
logger = logging.getLogger(__name__)


# The entity categories, taken from the schema so the two cannot drift.
ENTITY_CATEGORIES = tuple(ExtractedEntities.model_fields)

# What both analysis endpoints say the body is. One description so the two
# cannot describe the same multipart body differently.
BATCH_DESCRIPTION = (
    "The documents to summarise (PDF, DOCX, TXT). Several documents are "
    "taken to be about the same patient and merged into one summary."
)

# The generic failure, worded as the 500 body the non-streaming route sends.
INTERNAL_ERROR = "Internal server error"

# How the credential gate is documented on both analysis endpoints. It is
# middleware, so FastAPI cannot see it and would otherwise leave a deployment's
# 401 out of the schema entirely; and it is conditional, so the description says
# when it applies rather than asserting that every deployment refuses an
# anonymous caller.
UNAUTHORIZED_DESCRIPTION = (
    "No valid credential. Only a deployment that configures a shared credential "
    "answers this; one that does not never refuses for this reason."
)

# How a refusal is documented on the streaming endpoint. Declaring `model=`
# there would file the error shape under the route's own media type, which on
# that endpoint is text/event-stream - and a refusal is ordinary JSON, sent
# before any stream opens. The reference is written out because the schema is
# already in the document: every other route puts it there.
JSON_REFUSAL = {
    "content": {
        "application/json": {
            "schema": {"$ref": f"#/components/schemas/{ErrorResponse.__name__}"}
        }
    }
}

# What one event of the stream carries. FastAPI describes an SSE response with
# the generic event envelope and fills in the payload from the endpoint's return
# annotation - but it loses that annotation when the router is mounted under a
# prefix, and documents `data` as an untyped string. This states it instead, and
# is merged over whatever FastAPI generated, so the document describes what the
# endpoint actually sends.
#
# It is the document that gains, not today's generated client: openapi-typescript
# reads only `schema` from a media type, so the response body still types as
# `unknown` and a caller reaches the union through the generated
# `components["schemas"]["AnalysisEvent"]` instead. That name exists because of
# `response_model` below, which is the half of this that the frontend depends on.
STREAMED_EVENT_PAYLOAD = {
    "responses": {
        "200": {
            "content": {
                "text/event-stream": {
                    "itemSchema": {
                        "required": ["data"],
                        "properties": {
                            "data": {
                                "type": "string",
                                "contentMediaType": "application/json",
                                "contentSchema": {
                                    "$ref": (
                                        "#/components/schemas/"
                                        f"{AnalysisEvent.__name__}"
                                    )
                                },
                            }
                        },
                    }
                }
            }
        }
    }
}


async def accepted_batch(
    files: List[UploadFile] = File(..., description=BATCH_DESCRIPTION),
) -> List[UploadFile]:
    """
    Validate a submitted batch as a dependency, before the route body runs.

    The streaming route needs this: its body is an async generator, so by the
    time the first line of it runs the response has already been committed with
    a 200 and a refusal can no longer be a status code. Solving validation as a
    dependency keeps 400 and 413 answers on the stream endpoint identical to the
    ones `POST /api/analyze` sends.

    :param files: The uploaded documents.
    :return: The same files, once the whole batch has been accepted.
    :raises HTTPException: 400 for an empty batch or a rejected file, 413 for a
        file that is too large or a batch that holds too many.
    """
    await validate_batch(files)
    return files


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
        401: {"model": ErrorResponse, "description": UNAUTHORIZED_DESCRIPTION},
        413: {
            "model": ErrorResponse,
            "description": "A file is too large, or the batch holds too many files",
        },
        500: {"model": ErrorResponse, "description": "Internal server error"},
        503: {"model": ErrorResponse, "description": "The model is not loaded yet"},
    },
)
async def analyze(
    files: List[UploadFile] = Depends(accepted_batch),
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
            detail={"message": INTERNAL_ERROR},
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
            detail={"message": INTERNAL_ERROR},
        ) from exc


@router.post(
    "/analyze/stream",
    response_class=EventSourceResponse,
    # Puts the four event models in the document's schema section, which
    # STREAMED_EVENT_PAYLOAD then points the stream's `data` field at.
    response_model=AnalysisEvent,
    response_description="One event of the stream, its `data` an AnalysisEvent",
    openapi_extra=STREAMED_EVENT_PAYLOAD,
    dependencies=[Depends(require_the_model)],
    responses={
        400: {"description": "Invalid document", **JSON_REFUSAL},
        401: {"description": UNAUTHORIZED_DESCRIPTION, **JSON_REFUSAL},
        413: {
            "description": "A file is too large, or the batch holds too many files",
            **JSON_REFUSAL,
        },
        500: {
            "description": (
                "Internal server error, raised before the stream opened. A "
                "failure after that is a `result`-less `error` event instead."
            ),
            **JSON_REFUSAL,
        },
        503: {"description": "The model is not loaded yet", **JSON_REFUSAL},
    },
)
async def analyze_stream(
    files: List[UploadFile] = Depends(accepted_batch),
    text_extractor: TextExtractionServiceInterface = Depends(get_text_extractor),
    entity_extractor: EntityExtractionServiceInterface = Depends(get_entity_extractor),
) -> AsyncIterator[AnalysisEvent]:
    """
    Summarise documents as `POST /api/analyze` does, reporting progress as it goes.

    Same batch, same work, same answer: the final `result` event carries exactly
    the body the other endpoint returns. What this adds is the half minute
    before it. A `batch` event fixes how many documents were accepted, one
    `document` event lands as each is read, and the caller can show which of
    them is in flight instead of one spinner over the lot.

    The events are Server-Sent Events over the POST that carries the documents,
    so a browser reads them with `fetch` rather than `EventSource`, which only
    issues GETs. Each event's `data` is one JSON object tagged by `stage`.

    Nothing is stored, here or on the other endpoint. Progress events are
    content-free: a document is named by its submitted position, and nothing the
    model marked travels before the final result.

    A failure after the first event cannot be a status code - the response is
    committed the moment the stream opens - so it arrives as an `error` event
    with the wording the equivalent refusal would have carried, and the stream
    ends. Validation and readiness are settled before the stream opens, so a
    rejected file, an oversized batch and an unloaded model are still 400, 413
    and 503 with no events at all.

    Args:
        files: The uploaded documents (PDF, DOCX, TXT)

    Returns:
        The batch, one event per document read, and either a result or an error.

    Raises:
        HTTPException: 400 for an invalid file, 413 for a file or batch that is
            too large, 503 while the model is not loaded
    """
    yield AnalysisEvent(BatchStarted(total=len(files)))

    documents: List[ReadDocument] = []
    try:
        async for document in read_documents(files, text_extractor, entity_extractor):
            documents.append(document)
            # Read off `describe`, which is what the final result reports for
            # the same document, rather than deriving it a second time here.
            # `UnreadableReason` is meant to grow, and two derivations would
            # let a `document` event disagree with the `result` that follows it.
            reported = describe(document)
            yield AnalysisEvent(
                DocumentProgress(
                    index=len(documents) - 1,
                    read=reported.read,
                    unreadable_reason=reported.unreadable_reason,
                )
            )

        summary = summarize_read_documents(documents)
        # Built inside the guard for the same reason as on the other endpoint: a
        # malformed EntityDetail raises a pydantic error quoting the offending
        # value, which would be document content.
        completed = AnalysisEvent(
            AnalysisCompleted(
                result=AnalysisResponse(
                    summary=summary,
                    documents=[describe(document) for document in documents],
                    mapping_info=entity_extractor.get_mapping_info(),
                )
            )
        )
    except UnreadableDocument:
        # Every document already went out marked unread, so the caller can see
        # which ones. This says the batch has no summary to degrade to - the
        # streamed equivalent of the 400 the other endpoint answers.
        yield AnalysisEvent(
            AnalysisFailed(
                reason=FailureReason.UNREADABLE_BATCH, message=UNREADABLE_DOCUMENT
            )
        )
        return
    except ValidationError:
        logger.error("Analysis produced an unexpected entity shape")
        yield AnalysisEvent(
            AnalysisFailed(reason=FailureReason.SERVER_ERROR, message=INTERNAL_ERROR)
        )
        return
    except Exception as exc:  # pylint: disable=W0718
        # Broad on purpose, and narrower than it looks: an exception escaping an
        # async generator after the response is committed reaches no handler,
        # and the caller is left with a stream that stops mid-batch and no
        # reason. The type is logged, never sent.
        logger.error("Streamed analysis failed (%s)", type(exc).__name__)
        yield AnalysisEvent(
            AnalysisFailed(reason=FailureReason.SERVER_ERROR, message=INTERNAL_ERROR)
        )
        return

    yield completed
