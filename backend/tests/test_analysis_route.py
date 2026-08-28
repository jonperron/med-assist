# pylint: disable=W0621
import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.analysis import router
from app.core.dependencies import get_entity_extractor, get_text_extractor
from app.interfaces.service_interfaces import (
    EntityExtractionServiceInterface,
    TextExtractionServiceInterface,
)
from app.schemas.errors import ErrorDetail
from app.schemas.extraction import EntityDetail
from app.use_cases.validate_file import MAX_BATCH_FILES

TEXT = "Le homme de 67 ans a de la fièvre"
TXT_FILE = ("note.txt", b"Le homme de 67 ans a de la fievre", "text/plain")


def txt(name="note.txt"):
    return ("files", (name, b"contenu", "text/plain"))


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


def test_analyze_summarises_one_document(client):
    response = client.post("/api/analyze", files=[txt()])

    assert response.status_code == 200
    summary = response.json()["summary"]
    assert summary["patient"] == "Patient, 67 ans, homme."
    assert summary["document_count"] == 1
    headings = {section["key"]: section for section in summary["sections"]}
    assert headings["pathologies"]["sentence"] == "Grippe."
    assert headings["symptoms"]["findings"] == [{"text": "fièvre", "documents": [0]}]


def test_sections_are_ordered_for_reading(client):
    summary = client.post("/api/analyze", files=[txt()]).json()["summary"]

    # Pathologies before symptoms: the diagnosis leads, the presentation follows.
    assert [section["key"] for section in summary["sections"]] == [
        "pathologies",
        "symptoms",
    ]


def test_analyze_merges_several_documents_into_one_summary(client):
    response = client.post("/api/analyze", files=[txt("a.txt"), txt("b.txt")])

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["document_count"] == 2
    # The same finding in both documents is reported once.
    sections = {section["key"]: section for section in body["summary"]["sections"]}
    assert sections["symptoms"]["findings"] == [{"text": "fièvre", "documents": [0, 1]}]
    # The per-document detail is still there for a caller that wants it.
    assert len(body["documents"]) == 2


def test_no_confidence_score_reaches_the_summary(client):
    summary = client.post("/api/analyze", files=[txt()]).json()["summary"]

    rendered = repr(summary)
    assert "%" not in rendered
    assert "score" not in rendered


def test_analyze_does_not_echo_the_document_text(client):
    body = client.post("/api/analyze", files=[txt()]).json()

    assert "text" not in body
    assert TEXT not in repr(body)


def test_analyze_never_stores_anything(client):
    body = client.post("/api/analyze", files=[txt()]).json()

    # Nothing to come back for: no identifier is issued.
    assert "file_id" not in body
    assert "expires_in_seconds" not in body


def test_analyze_reports_an_empty_summary_rather_than_an_empty_page(
    client, mock_entity_extractor
):
    mock_entity_extractor.extract_entities = AsyncMock(return_value={})

    summary = client.post("/api/analyze", files=[txt()]).json()["summary"]

    assert summary["empty"] is True
    assert summary["sections"] == []
    assert summary["patient"] is None


def test_analyze_rejects_an_unsupported_file_type(client):
    response = client.post(
        "/api/analyze", files=[("files", ("note.exe", b"binary", "application/exe"))]
    )

    assert response.status_code == 400


def test_analyze_rejects_an_oversized_batch(client):
    files = [txt(f"note{index}.txt") for index in range(MAX_BATCH_FILES + 1)]

    response = client.post("/api/analyze", files=files)

    assert response.status_code == 413
    assert response.json()["detail"]["max_files"] == MAX_BATCH_FILES


def test_a_rejected_batch_is_never_partly_analysed(client, mock_entity_extractor):
    files = [txt("ok.txt"), ("files", ("bad.exe", b"binary", "application/exe"))]

    response = client.post("/api/analyze", files=files)

    assert response.status_code == 400
    mock_entity_extractor.extract_entities.assert_not_called()


def test_analyze_reports_an_empty_document(client, mock_text_extractor):
    mock_text_extractor.extract_text = AsyncMock(return_value="")

    response = client.post("/api/analyze", files=[txt()])

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == (
        "Unable to extract text from the document."
    )


def test_a_failing_document_does_not_name_itself(client, mock_text_extractor):
    mock_text_extractor.extract_text = AsyncMock(return_value="")

    body = client.post("/api/analyze", files=[txt("compte-rendu-Dupont.txt")]).json()

    assert "Dupont" not in repr(body)


def test_analyze_hides_internal_failures(client, mock_entity_extractor, caplog):
    mock_entity_extractor.extract_entities = AsyncMock(
        side_effect=RuntimeError("model crashed on 'Le homme a de la fièvre'")
    )

    response = client.post("/api/analyze", files=[txt()])

    assert response.status_code == 500
    assert response.json()["detail"] == {"message": "Internal server error"}
    # Neither the document content nor the filename reaches the log.
    assert "homme" not in caplog.text
    assert "note.txt" not in caplog.text


class TestMalformedRequests:
    """
    A malformed request must not be answered with the value it was rejected for.

    On this route the body is the documents, so FastAPI's own validation
    handler - which reports the rejected value under an `input` key - would
    reflect clinical text back to the sender, outside the fixed envelope every
    other refusal on this service uses.
    """

    @pytest.fixture
    def app_client(self, mock_text_extractor, mock_entity_extractor):
        from app.main import malformed_requests_stay_generic
        from fastapi.exceptions import RequestValidationError

        app = FastAPI()
        app.include_router(router, prefix="/api")
        app.add_exception_handler(
            RequestValidationError, malformed_requests_stay_generic
        )
        app.dependency_overrides[get_text_extractor] = lambda: mock_text_extractor
        app.dependency_overrides[get_entity_extractor] = lambda: mock_entity_extractor
        return TestClient(app)

    def test_a_text_part_sent_as_a_document_is_not_echoed(self, app_client):
        response = app_client.post(
            "/api/analyze", data={"files": "PATIENT Jean DUPONT 12/03/1958"}
        )

        assert response.status_code == 422
        assert "DUPONT" not in response.text
        assert "input" not in response.json()["detail"]

    def test_a_malformed_request_uses_the_same_envelope_as_every_refusal(
        self, app_client
    ):
        body = app_client.post("/api/analyze", data={"files": "x"}).json()

        # {"detail": {"message": ...}} is what the frontend parses.
        ErrorDetail(**body["detail"])


class TestDocumentDates:
    """
    A date is what a clinician places a document by, so the answer carries one.

    The date is read from the document's own head, per document, and the batch
    reports the stretch its dated documents cover. A document with no date in
    its head says so rather than borrowing one.
    """

    def test_a_document_reports_the_date_it_carries(self, client, mock_text_extractor):
        mock_text_extractor.extract_text = AsyncMock(
            return_value="Le 4 mars 2024\n" + TEXT
        )

        body = client.post("/api/analyze", files=[txt()]).json()

        assert body["documents"][0]["document_date"] == "2024-03-04"
        assert body["summary"]["date_range"] == {
            "start": "2024-03-04",
            "end": "2024-03-04",
        }

    def test_an_undated_document_says_so_rather_than_guessing(self, client):
        body = client.post("/api/analyze", files=[txt()]).json()

        # The fixture text carries no date at all.
        assert body["documents"][0]["document_date"] is None
        assert body["summary"]["date_range"] is None

    def test_the_range_runs_across_the_batch(self, client, mock_text_extractor):
        mock_text_extractor.extract_text = AsyncMock(
            side_effect=[
                "Le 2 avril 2024\n" + TEXT,
                TEXT,
                "Le 4 mars 2024\n" + TEXT,
            ]
        )

        body = client.post(
            "/api/analyze", files=[txt("a.txt"), txt("b.txt"), txt("c.txt")]
        ).json()

        assert [document["document_date"] for document in body["documents"]] == [
            "2024-04-02",
            None,
            "2024-03-04",
        ]
        assert body["summary"]["date_range"] == {
            "start": "2024-03-04",
            "end": "2024-04-02",
        }

    def test_an_unread_document_carries_no_date(self, client, mock_text_extractor):
        mock_text_extractor.extract_text = AsyncMock(
            side_effect=["", "Le 4 mars 2024\n" + TEXT]
        )

        documents = client.post(
            "/api/analyze", files=[txt("a.txt"), txt("b.txt")]
        ).json()["documents"]

        assert documents[0]["document_date"] is None
        assert documents[1]["document_date"] == "2024-03-04"

    def test_a_date_of_birth_in_the_head_is_not_reported_as_the_document_date(
        self, client, mock_text_extractor
    ):
        # It would be wrong by decades, and it is a patient identifier.
        mock_text_extractor.extract_text = AsyncMock(
            return_value="Née le 12/05/1948\n" + TEXT
        )

        body = client.post("/api/analyze", files=[txt()]).json()

        assert body["documents"][0]["document_date"] is None
        assert "1948" not in repr(body)


class TestPartialBatches:
    """
    One document that cannot be read no longer costs the batch its summary.

    A summary of three documents out of four, marked as such, is worth more to
    a clinician than a refusal - as long as the answer says which one is
    missing. It says it by position, which is the caller's own file order: the
    filename that would name it directly must not leave the server.
    """

    def test_a_readable_document_is_still_summarised_beside_an_unreadable_one(
        self, client, mock_text_extractor
    ):
        mock_text_extractor.extract_text = AsyncMock(side_effect=[TEXT, ""])

        response = client.post("/api/analyze", files=[txt("a.txt"), txt("b.txt")])

        assert response.status_code == 200
        body = response.json()
        assert body["summary"]["empty"] is False
        assert body["summary"]["document_count"] == 1

    def test_the_unread_document_keeps_its_submitted_position(
        self, client, mock_text_extractor
    ):
        mock_text_extractor.extract_text = AsyncMock(side_effect=["", TEXT])

        documents = client.post(
            "/api/analyze", files=[txt("a.txt"), txt("b.txt")]
        ).json()["documents"]

        assert [document["read"] for document in documents] == [False, True]
        assert documents[0]["unreadable_reason"] == "no_text"
        assert documents[1]["unreadable_reason"] is None
        # The findings index the same list, so the caller can resolve both.
        assert documents[0]["symptoms"] == []

    def test_a_finding_points_at_the_document_that_carried_it(
        self, client, mock_text_extractor
    ):
        mock_text_extractor.extract_text = AsyncMock(side_effect=["", TEXT])

        summary = client.post(
            "/api/analyze", files=[txt("a.txt"), txt("b.txt")]
        ).json()["summary"]

        sections = {section["key"]: section for section in summary["sections"]}
        assert sections["symptoms"]["findings"] == [
            {"text": "fièvre", "documents": [1]}
        ]

    def test_a_batch_nothing_could_be_read_from_is_still_refused(
        self, client, mock_text_extractor
    ):
        mock_text_extractor.extract_text = AsyncMock(return_value="")

        response = client.post("/api/analyze", files=[txt("a.txt"), txt("b.txt")])

        assert response.status_code == 400
        assert response.json()["detail"]["message"] == (
            "Unable to extract text from the document."
        )

    def test_a_partial_answer_does_not_name_the_document_that_failed(
        self, client, mock_text_extractor
    ):
        mock_text_extractor.extract_text = AsyncMock(side_effect=[TEXT, ""])

        body = client.post(
            "/api/analyze",
            files=[txt("ok.txt"), txt("compte-rendu-Dupont.pdf")],
        ).json()

        assert "Dupont" not in repr(body)
        assert "compte-rendu" not in repr(body)

    def test_document_count_and_the_document_list_diverge_when_one_is_unread(
        self, client, mock_text_extractor
    ):
        # `document_count` is how many were read; `documents` reports every
        # submission, read or not - the two are not the same number once a
        # document in the middle of the batch fails.
        mock_text_extractor.extract_text = AsyncMock(side_effect=[TEXT, "", TEXT])

        body = client.post(
            "/api/analyze", files=[txt("a.txt"), txt("b.txt"), txt("c.txt")]
        ).json()

        assert body["summary"]["document_count"] == 2
        assert len(body["documents"]) == 3
        assert [document["read"] for document in body["documents"]] == [
            True,
            False,
            True,
        ]

    def test_a_document_the_parser_could_not_open_is_reported_the_same_way(
        self, client, mock_text_extractor
    ):
        # The parser's own message quotes the bytes that failed, so a corrupt
        # file must reach the caller as a position, not as an exception.
        mock_text_extractor.extract_text = AsyncMock(
            side_effect=[TEXT, ValueError("cannot parse 'Jean DUPONT 12/03/1958'")]
        )

        response = client.post("/api/analyze", files=[txt("a.txt"), txt("b.pdf")])

        assert response.status_code == 200
        assert response.json()["documents"][1]["read"] is False
        assert "DUPONT" not in response.text

    def test_a_failure_that_is_not_the_document_is_still_a_server_error(
        self, client, mock_entity_extractor
    ):
        mock_entity_extractor.extract_entities = AsyncMock(
            side_effect=ValueError("model configuration is wrong")
        )

        response = client.post("/api/analyze", files=[txt()])

        assert response.status_code == 500
        assert response.json()["detail"] == {"message": "Internal server error"}


class TestTheEntityPayloadIsUntouched:
    """
    Pairing shapes the summary, not the per-document entities behind it.

    The summarizer joins an examination to its value on a copy. If that copy
    ever reached `documents`, a caller reading `examinations[0].text` would get
    a span that is not in the document, at offsets that no longer index it.
    """

    @pytest.fixture
    def paired(self):
        return {
            "examinations": [
                EntityDetail(
                    text="Troponine I", label="examen", score=0.9, start=0, end=11
                )
            ],
            "measurements": [
                EntityDetail(
                    text="1,10 ng/mL", label="valeur", score=0.9, start=14, end=24
                )
            ],
        }

    def test_the_summary_pairs_them_and_the_payload_does_not(
        self, client, mock_entity_extractor, paired
    ):
        mock_entity_extractor.extract_entities = AsyncMock(return_value=paired)

        body = client.post("/api/analyze", files=[txt()]).json()

        sections = {section["key"]: section for section in body["summary"]["sections"]}
        assert sections["examinations"]["findings"] == [
            {"text": "Troponine I 1,10 ng/mL", "documents": [0]}
        ]
        # The document still reports the span the model actually marked.
        examination = body["documents"][0]["examinations"][0]
        assert examination["text"] == "Troponine I"
        assert (examination["start"], examination["end"]) == (0, 11)


def test_an_unexpected_entity_shape_is_a_server_error(
    client, mock_entity_extractor, caplog
):
    # A pydantic error quotes the value it rejected, which here would be
    # document content, so this branch must never forward what it caught.
    #
    # The category has to be one the summarizer never inspects. Under a section
    # category the malformed entry is reached first, as an AttributeError on a
    # plain dict, and the generic handler answers instead - the same 500 for a
    # different reason, which would leave this branch untested while green.
    mock_entity_extractor.extract_entities = AsyncMock(
        return_value={"temporal": [{"text": "fièvre", "label": "moment"}]}
    )

    response = client.post("/api/analyze", files=[txt()])

    assert response.status_code == 500
    assert response.json()["detail"] == {"message": "Internal server error"}
    assert "fièvre" not in response.text
    # Pinned by its log line rather than by the status code, which the generic
    # handler produces too: this asserts which branch answered.
    assert "unexpected entity shape" in caplog.text
    assert "fièvre" not in caplog.text


def test_a_skipped_document_is_logged_by_position_only(
    client, mock_text_extractor, caplog
):
    mock_text_extractor.extract_text = AsyncMock(side_effect=[TEXT, ""])

    client.post("/api/analyze", files=[txt("ok.txt"), txt("Dupont-scan.pdf")])

    # There has to be a signal that a document was dropped, and it has to carry
    # neither the filename nor anything the document said.
    assert "yielded no text" in caplog.text
    assert "Dupont" not in caplog.text
    assert "homme" not in caplog.text
