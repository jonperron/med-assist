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
    assert headings["symptoms"]["findings"] == ["fièvre"]


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
    assert sections["symptoms"]["findings"] == ["fièvre"]
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

    assert body["retained"] is False
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
