"""`AnalysisEvent` wraps four event shapes, and should disappear on the wire.

The route yields `AnalysisEvent(...)` so a caller cannot construct an event
that lacks a `stage`, but nothing about that wrapper - no `root` key, no
envelope - is meant to reach a client. These tests pin that down at the schema
level, independent of the streaming route that happens to be its only caller
today.
"""

import pytest
from pydantic import ValidationError

from app.schemas.errors import UNREADABLE_DOCUMENT
from app.schemas.extraction import AnalysisResponse, UnreadableReason
from app.schemas.progress import (
    AnalysisCompleted,
    AnalysisEvent,
    AnalysisFailed,
    BatchStarted,
    DocumentProgress,
    FailureReason,
)
from app.schemas.summary import ClinicalSummary


def minimal_result() -> AnalysisResponse:
    return AnalysisResponse(
        summary=ClinicalSummary(
            patient="Patient.", document_count=0, sections=[], date_range=None
        ),
        documents=[],
        mapping_info={},
    )


class TestSerializesToTheInnerEvent:
    """No envelope survives `model_dump`/`model_dump_json`."""

    def test_a_batch_event_serialises_flat(self):
        dumped = AnalysisEvent(BatchStarted(total=3)).model_dump()

        assert dumped == {"stage": "batch", "total": 3}
        assert "root" not in dumped

    def test_a_document_event_serialises_flat(self):
        dumped = AnalysisEvent(
            DocumentProgress(index=1, read=False, unreadable_reason=None)
        ).model_dump()

        assert dumped == {
            "stage": "document",
            "index": 1,
            "read": False,
            "unreadable_reason": None,
        }

    def test_an_error_event_serialises_flat(self):
        dumped = AnalysisEvent(
            AnalysisFailed(
                reason=FailureReason.UNREADABLE_BATCH, message=UNREADABLE_DOCUMENT
            )
        ).model_dump()

        assert dumped == {
            "stage": "error",
            "reason": FailureReason.UNREADABLE_BATCH,
            "message": UNREADABLE_DOCUMENT,
        }

    def test_an_error_event_must_say_which_kind_of_failure_it_is(self):
        # `reason` stands in for the status code the stream cannot send, so it
        # is required rather than defaulted to either kind.
        with pytest.raises(ValidationError):
            AnalysisFailed(message=UNREADABLE_DOCUMENT)

    def test_an_event_refuses_a_field_the_schema_does_not_name(self):
        # The progress channel is content-free because these models are closed.
        # A field added beside a parser has to be added here, deliberately.
        with pytest.raises(ValidationError):
            BatchStarted(total=1, text="Le homme de 67 ans a de la fievre")

    def test_a_result_event_wraps_exactly_the_analysis_response(self):
        result = minimal_result()

        dumped = AnalysisEvent(AnalysisCompleted(result=result)).model_dump()

        assert dumped == {"stage": "result", "result": result.model_dump()}

    def test_model_dump_json_carries_no_root_key(self):
        payload = AnalysisEvent(BatchStarted(total=1)).model_dump_json()

        assert '"root"' not in payload
        assert payload.startswith('{"stage"')


class TestParsingBackFromTheWire:
    """The discriminator resolves a bare dict to the right event, not a union."""

    def test_a_batch_payload_parses_to_batch_started(self):
        event = AnalysisEvent.model_validate({"stage": "batch", "total": 2})

        assert isinstance(event.root, BatchStarted)
        assert event.root.total == 2

    def test_a_document_payload_parses_to_document_progress(self):
        event = AnalysisEvent.model_validate(
            {
                "stage": "document",
                "index": 0,
                "read": False,
                "unreadable_reason": UnreadableReason.NO_TEXT.value,
            }
        )

        assert isinstance(event.root, DocumentProgress)
        assert event.root.unreadable_reason == UnreadableReason.NO_TEXT

    def test_an_unknown_stage_is_rejected(self):
        with pytest.raises(ValidationError):
            AnalysisEvent.model_validate({"stage": "progress", "total": 1})
