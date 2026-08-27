"""The streamed analysis: the same answer, with the wait made legible.

`POST /api/analyze/stream` exists so a caller can say "2 of 4" instead of
holding one spinner over the whole batch. Two things are asserted throughout:
the final result is byte-for-byte what `POST /api/analyze` would have answered,
and nothing before it carries document content.

`TestClient` collects the whole ASGI body before handing back a response, so
these tests read a finished stream. Incremental delivery is a property of the
server, not of the contract, and is not asserted here - a timing assertion
written against `TestClient` would fail for a reason that has nothing to do with
the endpoint.

A client disconnecting mid-stream is the one thing `TestClient` cannot produce
at all, finished or not: `TestClientDisconnectMidStream` calls the route's
generator directly and closes it, the way Starlette closes it when the
connection drops.
"""

# pylint: disable=W0621
import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.analysis import analyze_stream, router
from app.core.dependencies import get_entity_extractor, get_text_extractor
from app.core.middleware import MAX_REQUEST_SIZE_BYTES
from app.interfaces.service_interfaces import (
    EntityExtractionServiceInterface,
    TextExtractionServiceInterface,
)
from app.main import PRODUCTION, create_app
from app.schemas.errors import UNREADABLE_DOCUMENT, ErrorDetail
from app.schemas.extraction import EntityDetail
from app.use_cases.validate_file import MAX_BATCH_FILES

TEXT = "Le homme de 67 ans a de la fièvre"

STREAM = "/api/analyze/stream"


def txt(name="note.txt"):
    return ("files", (name, b"contenu", "text/plain"))


def events(response):
    """The `data:` payloads of a finished stream, decoded, in order."""
    assert response.headers["content-type"].startswith("text/event-stream")
    return [
        json.loads(line.removeprefix("data:").strip())
        for line in response.text.splitlines()
        if line.startswith("data:")
    ]


def stages(response, stage):
    return [event for event in events(response) if event["stage"] == stage]


@pytest.fixture
def mock_text_extractor():
    mock = MagicMock(spec=TextExtractionServiceInterface)
    mock.extract_text = AsyncMock(return_value=TEXT)
    return mock


@pytest.fixture
def entities():
    return {
        "patient_info": [
            EntityDetail(text="67 ans", label="age", score=0.9, start=12, end=18),
            EntityDetail(text="homme", label="genre", score=0.9, start=3, end=8),
        ],
        "symptoms": [
            EntityDetail(text="fièvre", label="sosy", score=0.8, start=27, end=33)
        ],
        "pathologies": [EntityDetail(text="grippe", label="pathologie", score=0.95)],
    }


@pytest.fixture
def mock_entity_extractor(entities):
    mock = MagicMock(spec=EntityExtractionServiceInterface)
    mock.extract_entities = AsyncMock(return_value=entities)
    mock.get_mapping_info.return_value = {"language": "fr", "dataset": "cas"}
    return mock


@pytest.fixture
def client(mock_text_extractor, mock_entity_extractor):
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_text_extractor] = lambda: mock_text_extractor
    app.dependency_overrides[get_entity_extractor] = lambda: mock_entity_extractor
    return TestClient(app)


class TestProgress:
    """What the caller learns before the answer arrives."""

    def test_the_batch_is_announced_before_any_document_is_read(self, client):
        first = events(client.post(STREAM, files=[txt(), txt()]))[0]

        # The count a "2 of 4" counter divides by, and confirmation that the
        # whole batch passed validation.
        assert first == {"stage": "batch", "total": 2}

    def test_every_document_is_reported_once_in_submission_order(self, client):
        response = client.post(STREAM, files=[txt("a.txt"), txt("b.txt"), txt("c.txt")])

        assert [event["index"] for event in stages(response, "document")] == [0, 1, 2]

    def test_a_read_document_is_reported_as_read(self, client):
        [document] = stages(client.post(STREAM, files=[txt()]), "document")

        assert document == {
            "stage": "document",
            "index": 0,
            "read": True,
            "unreadable_reason": None,
        }

    def test_progress_ends_with_exactly_one_answer(self, client):
        response = client.post(STREAM, files=[txt(), txt()])

        assert [event["stage"] for event in events(response)] == [
            "batch",
            "document",
            "document",
            "result",
        ]

    def test_progress_carries_nothing_the_documents_said(self, client):
        response = client.post(STREAM, files=[txt("Dupont-scan.txt")])

        # Everything before the result is positions and counts. The filename
        # the caller posted does not come back, and neither does the text.
        before_result = response.text.split('"stage": "result"')[0]
        assert "Dupont" not in before_result
        assert "fièvre" not in before_result
        assert "grippe" not in before_result


class TestTheAnswer:
    """The stream answers the same question as the endpoint beside it."""

    def test_the_result_is_what_the_plain_endpoint_would_have_answered(self, client):
        streamed = stages(client.post(STREAM, files=[txt(), txt()]), "result")
        plain = client.post("/api/analyze", files=[txt(), txt()])

        assert [event["result"] for event in streamed] == [plain.json()]

    def test_parity_holds_where_a_document_could_not_be_read(
        self, client, mock_text_extractor
    ):
        # The clean-batch comparison above cannot drift; these can. A partial
        # batch exercises the unread placeholder, the shortened document_count
        # and the per-document read flags on both paths at once.
        mock_text_extractor.extract_text = AsyncMock(side_effect=[TEXT, "", TEXT])
        streamed = stages(client.post(STREAM, files=[txt(), txt(), txt()]), "result")

        mock_text_extractor.extract_text = AsyncMock(side_effect=[TEXT, "", TEXT])
        plain = client.post("/api/analyze", files=[txt(), txt(), txt()])

        assert [event["result"] for event in streamed] == [plain.json()]

    def test_parity_holds_for_a_dated_document(self, client, mock_text_extractor):
        dated = "Le 4 mars 2024\n" + TEXT

        mock_text_extractor.extract_text = AsyncMock(return_value=dated)
        streamed = stages(client.post(STREAM, files=[txt()]), "result")

        mock_text_extractor.extract_text = AsyncMock(return_value=dated)
        plain = client.post("/api/analyze", files=[txt()])

        assert [event["result"] for event in streamed] == [plain.json()]

    def test_the_summary_is_built_from_every_document_read(self, client):
        [completed] = stages(client.post(STREAM, files=[txt(), txt()]), "result")

        summary = completed["result"]["summary"]
        assert summary["patient"] == "Patient, 67 ans, homme."
        assert summary["document_count"] == 2

    def test_a_document_date_reaches_the_caller_with_the_result(
        self, client, mock_text_extractor
    ):
        mock_text_extractor.extract_text = AsyncMock(
            return_value="Le 4 mars 2024\n" + TEXT
        )

        [completed] = stages(client.post(STREAM, files=[txt()]), "result")

        # The date is part of the answer, not of the progress channel: a
        # progress event says how far along the batch is and nothing else.
        assert completed["result"]["documents"][0]["document_date"] == "2024-03-04"


class TestPartialBatches:
    """A document that cannot be read is reported, and the batch carries on."""

    def test_an_unreadable_document_is_reported_as_it_is_skipped(
        self, client, mock_text_extractor
    ):
        mock_text_extractor.extract_text = AsyncMock(side_effect=[TEXT, ""])

        response = client.post(STREAM, files=[txt("ok.txt"), txt("scan.txt")])

        assert stages(response, "document")[1] == {
            "stage": "document",
            "index": 1,
            "read": False,
            "unreadable_reason": "no_text",
        }

    def test_the_batch_still_answers_with_what_it_could_read(
        self, client, mock_text_extractor
    ):
        mock_text_extractor.extract_text = AsyncMock(side_effect=[TEXT, ""])

        [completed] = stages(
            client.post(STREAM, files=[txt(), txt()]),
            "result",
        )

        assert completed["result"]["summary"]["document_count"] == 1
        assert [document["read"] for document in completed["result"]["documents"]] == [
            True,
            False,
        ]

    def test_a_batch_nothing_could_be_read_from_ends_in_an_error(
        self, client, mock_text_extractor
    ):
        mock_text_extractor.extract_text = AsyncMock(return_value="")

        response = client.post(STREAM, files=[txt(), txt()])

        # The two documents still went out marked unread, so the caller can
        # show which ones failed. Then the batch says it has no summary.
        assert [event["stage"] for event in events(response)] == [
            "batch",
            "document",
            "document",
            "error",
        ]
        assert stages(response, "error") == [
            {
                "stage": "error",
                "reason": "unreadable_batch",
                "message": UNREADABLE_DOCUMENT,
            }
        ]

    def test_an_unreadable_first_document_does_not_stop_later_ones_being_read(
        self, client, mock_text_extractor
    ):
        # The order matters: a batch that only tolerates a failure at the end
        # would be a narrower guarantee than "the batch carries on".
        mock_text_extractor.extract_text = AsyncMock(
            side_effect=["", TEXT, TEXT]
        )

        response = client.post(
            STREAM, files=[txt("scan.txt"), txt("a.txt"), txt("b.txt")]
        )

        assert [event["read"] for event in stages(response, "document")] == [
            False,
            True,
            True,
        ]
        [completed] = stages(response, "result")
        assert completed["result"]["summary"]["document_count"] == 2
        assert [
            document["read"] for document in completed["result"]["documents"]
        ] == [False, True, True]

    def test_the_reason_tells_a_caller_fault_from_a_server_fault(
        self, client, mock_text_extractor, mock_entity_extractor
    ):
        mock_text_extractor.extract_text = AsyncMock(return_value="")
        unreadable = stages(client.post(STREAM, files=[txt()]), "error")

        mock_text_extractor.extract_text = AsyncMock(return_value=TEXT)
        mock_entity_extractor.extract_entities = AsyncMock(side_effect=RuntimeError())
        faulted = stages(client.post(STREAM, files=[txt()]), "error")

        # The status codes the stream cannot send: 400 on the caller's document
        # against 500 on the service's own failure. A client branches on this
        # rather than on wording that may be translated.
        assert unreadable[0]["reason"] == "unreadable_batch"
        assert faulted[0]["reason"] == "server_error"

    def test_the_wording_matches_the_refusal_the_plain_endpoint_sends(
        self, client, mock_text_extractor
    ):
        mock_text_extractor.extract_text = AsyncMock(return_value="")

        streamed = stages(client.post(STREAM, files=[txt()]), "error")
        refused = client.post("/api/analyze", files=[txt()])

        assert refused.status_code == 400
        assert streamed[0]["message"] == refused.json()["detail"]["message"]


class TestRefusalsBeforeTheStreamOpens:
    """
    Validation is a dependency, so a refusal is still a status code.

    Once the first event is written the response is committed at 200, and a
    refusal can only be an event. Everything knowable up front - the file types,
    the sizes, the batch cap - is therefore settled before the generator runs,
    so these answer exactly as `POST /api/analyze` does.
    """

    def test_a_rejected_file_type_is_a_400_with_no_events(self, client):
        response = client.post(
            STREAM, files=[("files", ("virus.exe", b"x", "application/x-msdownload"))]
        )

        assert response.status_code == 400
        assert response.headers["content-type"].startswith("application/json")
        ErrorDetail(**response.json()["detail"])

    def test_an_empty_batch_is_refused_exactly_as_the_plain_endpoint_refuses_it(
        self, client
    ):
        streamed = client.post(STREAM, files=[])
        plain = client.post("/api/analyze", files=[])

        # Pinned as equality rather than as a status code: an empty batch is
        # the one refusal the two endpoints could plausibly answer differently,
        # since neither route body runs and FastAPI decides it.
        assert streamed.status_code == plain.status_code
        assert streamed.json() == plain.json()
        assert not streamed.headers["content-type"].startswith("text/event-stream")

    def test_too_many_files_is_a_413_with_no_events(self, client):
        response = client.post(STREAM, files=[txt()] * (MAX_BATCH_FILES + 1))

        assert response.status_code == 413
        assert response.json()["detail"]["max_files"] == MAX_BATCH_FILES

    def test_an_unloaded_model_is_a_503_with_no_events(
        self, mock_text_extractor, mock_entity_extractor
    ):
        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.dependency_overrides[get_text_extractor] = lambda: mock_text_extractor
        app.dependency_overrides[get_entity_extractor] = lambda: mock_entity_extractor
        app.state.model_loaded = False

        response = TestClient(app).post(STREAM, files=[txt()])

        assert response.status_code == 503
        ErrorDetail(**response.json()["detail"])


class TestFailuresMidStream:
    """A failure after the first event says so without quoting the document."""

    def test_an_unexpected_entity_shape_ends_the_stream_generically(
        self, client, mock_entity_extractor, caplog
    ):
        # A pydantic error quotes the value it rejected, which here would be
        # document content. The category is one the summarizer never inspects,
        # so the shape survives to the response model - see the equivalent test
        # on the plain endpoint for why that matters.
        mock_entity_extractor.extract_entities = AsyncMock(
            return_value={"temporal": [{"text": "fièvre", "label": "moment"}]}
        )

        response = client.post(STREAM, files=[txt()])

        assert stages(response, "error") == [
            {
                "stage": "error",
                "reason": "server_error",
                "message": "Internal server error",
            }
        ]
        assert stages(response, "result") == []
        assert "fièvre" not in response.text
        assert "unexpected entity shape" in caplog.text
        assert "fièvre" not in caplog.text

    def test_a_failure_in_extraction_ends_the_stream_generically(
        self, client, mock_entity_extractor, caplog
    ):
        mock_entity_extractor.extract_entities = AsyncMock(
            side_effect=RuntimeError("model died reading Jean DUPONT")
        )

        response = client.post(STREAM, files=[txt()])

        assert stages(response, "error") == [
            {
                "stage": "error",
                "reason": "server_error",
                "message": "Internal server error",
            }
        ]
        # Neither the exception message nor anything it quoted travels.
        assert "DUPONT" not in response.text
        assert "model died" not in response.text
        assert "RuntimeError" in caplog.text
        assert "DUPONT" not in caplog.text


class TestClientDisconnectMidStream:
    """
    A caller that goes away is not a failure the endpoint has to report.

    `TestClient` cannot simulate a dropped connection - it reads a finished
    stream - so these call the route's async generator directly. Closing it
    mid-iteration is exactly what Starlette does to the generator behind an
    `EventSourceResponse` when the client disconnects.
    """

    @pytest.mark.asyncio
    async def test_closing_the_stream_stops_it_from_reading_further_documents(
        self, mock_text_extractor, mock_entity_extractor
    ):
        generator = analyze_stream(
            files=[object(), object(), object()],
            text_extractor=mock_text_extractor,
            entity_extractor=mock_entity_extractor,
        )

        await generator.__anext__()  # the "batch" event
        await generator.__anext__()  # the first "document" event

        await generator.aclose()

        # Only the document already reported was read; the caller left before
        # the rest, and disconnecting does not make the batch race to finish.
        assert mock_text_extractor.extract_text.await_count == 1

    @pytest.mark.asyncio
    async def test_closing_the_stream_raises_nothing_and_logs_nothing(
        self, mock_text_extractor, mock_entity_extractor, caplog
    ):
        generator = analyze_stream(
            files=[object(), object()],
            text_extractor=mock_text_extractor,
            entity_extractor=mock_entity_extractor,
        )

        await generator.__anext__()
        await generator.__anext__()

        await generator.aclose()  # raises if the generator swallows GeneratorExit

        # The broad `except Exception` guarding a mid-stream failure does not
        # see a disconnect: GeneratorExit is a BaseException, so it is not
        # mistaken for a server fault and reported as one.
        assert "Streamed analysis failed" not in caplog.text
        assert "Internal server error" not in caplog.text


class TestMiddlewareInteraction:
    """The streamed response passes through the same middleware as any other."""

    @pytest.fixture
    def full_app_client(self, mock_text_extractor, mock_entity_extractor):
        app = create_app(PRODUCTION)
        app.dependency_overrides[get_text_extractor] = lambda: mock_text_extractor
        app.dependency_overrides[get_entity_extractor] = lambda: mock_entity_extractor
        return TestClient(app)

    def test_a_streamed_result_is_marked_uncacheable(self, full_app_client):
        response = full_app_client.post(STREAM, files=[txt()])

        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
        assert response.headers["pragma"] == "no-cache"

    def test_a_streamed_error_event_is_still_marked_uncacheable(
        self, full_app_client, mock_text_extractor
    ):
        mock_text_extractor.extract_text = AsyncMock(return_value="")

        response = full_app_client.post(STREAM, files=[txt()])

        assert stages(response, "error")
        assert response.headers["cache-control"] == "no-store"

    def test_an_oversized_declared_body_is_refused_before_the_stream_opens(
        self, full_app_client
    ):
        response = full_app_client.post(
            STREAM,
            files=[txt()],
            headers={"content-length": str(MAX_REQUEST_SIZE_BYTES + 1)},
        )

        assert response.status_code == 413
        assert not response.headers["content-type"].startswith("text/event-stream")
        # The size refusal is wrapped by forbid_caching too, same as any answer.
        assert response.headers["cache-control"] == "no-store"
