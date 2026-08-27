"""What a streamed analysis says while it is still reading.

`POST /api/analyze` answers once, at the end. A batch of four documents takes
about half a minute on a CPU, and a caller watching a spinner cannot tell a slow
batch from a stalled one. These are the events the streaming variant sends in
the meantime.

Every event here is deliberately content-free. A document is named by the
position the caller submitted it at, never by its filename, and nothing the
model marked appears until the final result - the progress channel exists to say
how far along the batch is, and nothing about it needs to carry clinical text.
"""

from enum import Enum
from typing import Annotated, Any, Dict, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, RootModel

from app.schemas.extraction import AnalysisResponse, UnreadableReason


def require_the_stage(schema: Dict[str, Any]) -> None:
    """
    Mark `stage` required in the generated schema, though it has a default.

    Every event carries its own tag, so the field is defaulted rather than
    written out at each of the five construction sites. Pydantic reads that
    default as "optional" and leaves `stage` out of `required`, which for a
    discriminator is wrong twice over: OpenAPI requires the property a
    discriminator names to be required, and a generated client would type the
    one field it has to narrow on as possibly absent.
    """
    required = schema.setdefault("required", [])
    if "stage" not in required:
        required.append("stage")


class StreamedEvent(BaseModel):
    """
    What every event of a streamed analysis has in common.

    Closed to extra fields on purpose, and this is the enforcement rather than a
    formality. `response_model` on an SSE route documents the payload but does
    not filter it: FastAPI serialises whatever the endpoint yields. The only
    thing keeping document content out of the progress channel is therefore
    these definitions, so the next field someone adds beside a parser has to be
    added here, deliberately, rather than arriving as an extra.
    """

    model_config = ConfigDict(extra="forbid", json_schema_extra=require_the_stage)


class BatchStarted(StreamedEvent):
    """The batch was accepted and reading has begun."""

    stage: Literal["batch"] = "batch"
    total: int = Field(
        description=(
            "How many documents were accepted for this batch. The caller "
            "already knows what it posted; this confirms the whole batch "
            "passed validation, and is what the later `document` indices "
            "count towards."
        )
    )


class DocumentProgress(StreamedEvent):
    """One submitted document has been read, or found unreadable."""

    stage: Literal["document"] = "document"
    index: int = Field(
        description=(
            "Position of this document in the submitted batch, counting from "
            "zero. Documents are read in submission order, so this also "
            "indexes `AnalysisResponse.documents` in the final result."
        )
    )
    read: bool = Field(
        description=(
            "False when no text could be read from this document. It is then "
            "not behind the summary, and the batch carries on without it."
        )
    )
    unreadable_reason: Optional[UnreadableReason] = Field(
        description="Why the document could not be read. Null when it was read."
    )


class AnalysisCompleted(StreamedEvent):
    """The batch is finished, and this carries the answer."""

    stage: Literal["result"] = "result"
    result: AnalysisResponse = Field(
        description=(
            "Exactly the body `POST /api/analyze` would have returned for the "
            "same batch. The two endpoints answer the same question; only the "
            "moments before the answer differ."
        )
    )


class FailureReason(str, Enum):
    """
    What kind of failure ended the batch, for a caller that has to act on it.

    Closed, and content-free like `UnreadableReason` beside it. It stands in for
    the status code the stream cannot send once it has answered 200: on
    `POST /api/analyze` the same two failures are a 400 and a 500, which is the
    difference between "your document did not work, try another scan" and "the
    service failed, try again later". Those are different things to tell a
    clinician, and a client should not have to tell them apart by matching on
    English that may be translated.
    """

    UNREADABLE_BATCH = "unreadable_batch"
    SERVER_ERROR = "server_error"


class AnalysisFailed(StreamedEvent):
    """The batch ended without a summary."""

    stage: Literal["error"] = "error"
    reason: FailureReason = Field(
        description=(
            "What kind of failure this is, for a caller deciding what to do "
            "next. `unreadable_batch` is the caller's document and corresponds "
            "to the 400 `POST /api/analyze` answers; `server_error` is the "
            "service's own failure and corresponds to its 500."
        )
    )
    message: str = Field(
        description=(
            "Content-free description of the failure, worded as the equivalent "
            "refusal from `POST /api/analyze`, and meant for display. Branch on "
            "`reason` rather than on this - the wording may change or be "
            "translated, and the reason will not."
        )
    )


class AnalysisEvent(
    RootModel[
        Annotated[
            Union[BatchStarted, DocumentProgress, AnalysisCompleted, AnalysisFailed],
            Field(discriminator="stage"),
        ]
    ]
):
    """
    One event of a streamed analysis: whichever of the four this one is.

    A model rather than a bare union alias so the contract has a name of its
    own in the OpenAPI document, and so the generated TypeScript is a union a
    client narrows rather than a bag of optional fields. `stage` is the tag: a
    caller cannot read a `result` off an event that does not carry one.

    It serialises to the event it wraps, so nothing about the wrapper reaches
    the wire.
    """
