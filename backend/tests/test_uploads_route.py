# pylint: disable=W0621
import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.uploads import MAX_BATCH_FILES, router
from app.core.dependencies import get_file_handler, get_text_repository
from app.interfaces.repositories_interfaces import TextRepositoryInterface
from app.schemas.errors import UNREADABLE_DOCUMENT, ErrorDetail
from app.services.file_handler import FileHandler

TXT = ("report.txt", b"Le patient a de la fievre", "text/plain")
BAD_EXTENSION = ("report.exe", b"Le patient a de la fievre", "text/plain")


@pytest.fixture
def mock_file_handler():
    handler = MagicMock(spec=FileHandler)
    handler.process_file = AsyncMock(return_value=True)
    return handler


@pytest.fixture
def mock_repository():
    repository = MagicMock(spec=TextRepositoryInterface)
    repository.get_document_ttl = AsyncMock(return_value=3600)
    return repository


@pytest.fixture
def client(mock_file_handler, mock_repository):
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_file_handler] = lambda: mock_file_handler
    app.dependency_overrides[get_text_repository] = lambda: mock_repository
    return TestClient(app)


def test_batch_upload_answers_one_id_per_file(client, mock_file_handler):
    response = client.post(
        "/api/upload_documents/",
        files=[("files", TXT), ("files", ("second.txt", b"Toux seche", "text/plain"))],
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["file_ids"]) == 2
    assert len(set(body["file_ids"])) == 2
    assert mock_file_handler.process_file.await_count == 2


def test_batch_upload_stores_nothing_under_the_batch_id():
    # A batch key nothing can read is a patient-adjacent value living out a
    # retention window for no one. It stays deleted.
    assert not hasattr(TextRepositoryInterface, "save_batch")
    assert not hasattr(FileHandler, "process_batch")


def test_single_upload_mirrors_the_batch_success_shape(client, mock_file_handler):
    response = client.post("/api/upload_document/", files={"file": TXT})

    assert response.status_code == 200
    body = response.json()
    assert body["filename"] == "report.txt"
    assert body["expires_in_seconds"] == 3600
    mock_file_handler.process_file.assert_awaited_once()


def test_single_and_batch_reject_the_same_bad_extension_the_same_way(
    client, mock_file_handler
):
    # Both routes funnel through the same store_document helper, so a refusal
    # raised on purpose must reach the caller unchanged and never touch storage.
    single = client.post("/api/upload_document/", files={"file": BAD_EXTENSION})
    batch = client.post("/api/upload_documents/", files=[("files", BAD_EXTENSION)])

    assert single.status_code == 400
    assert batch.status_code == 400
    assert single.json()["detail"]["message"] == batch.json()["detail"]["message"]
    mock_file_handler.process_file.assert_not_awaited()


def test_batch_upload_rejects_a_batch_over_the_file_cap(client, mock_file_handler):
    files = [("files", TXT) for _ in range(MAX_BATCH_FILES + 1)]

    response = client.post("/api/upload_documents/", files=files)

    assert response.status_code == 413
    assert response.json()["detail"]["max_files"] == MAX_BATCH_FILES
    # The cap is enforced before any file is touched.
    mock_file_handler.process_file.assert_not_awaited()


def test_a_batch_with_one_bad_file_stores_none_of_it(client, mock_file_handler):
    # The refusal comes back without any file id, so anything already stored
    # would sit out its retention window with nobody able to delete it. The
    # whole batch is validated before a single file is stored.
    response = client.post(
        "/api/upload_documents/",
        files=[("files", TXT), ("files", BAD_EXTENSION)],
    )

    assert response.status_code == 400
    mock_file_handler.process_file.assert_not_awaited()


def test_an_unreadable_document_is_refused_the_way_analyze_refuses_it(
    client, mock_file_handler
):
    # /api/analyze answers 400 for a document it cannot parse. A corrupt PDF is
    # the caller's problem on both endpoints, and a 500 here would also make
    # server-error alerting fire on scanned paperwork.
    mock_file_handler.process_file = AsyncMock(
        side_effect=ValueError("Unable to extract text from the document")
    )

    response = client.post("/api/upload_document/", files={"file": TXT})

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == UNREADABLE_DOCUMENT


def test_a_document_with_no_text_is_refused_not_reported_as_a_server_fault(
    client, mock_file_handler
):
    mock_file_handler.process_file = AsyncMock(return_value=False)

    response = client.post("/api/upload_document/", files={"file": TXT})

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == UNREADABLE_DOCUMENT


def test_a_storage_failure_is_still_a_server_fault(client, mock_file_handler):
    # Only the document's own unreadability is the caller's fault; Redis being
    # down is not, and must not be reported as a bad request.
    mock_file_handler.process_file = AsyncMock(side_effect=RuntimeError("redis down"))

    response = client.post("/api/upload_document/", files={"file": TXT})

    assert response.status_code == 500
    assert response.json()["detail"]["message"] == "Internal server error"


def test_a_refused_file_answers_a_body_the_schema_describes(client):
    response = client.post("/api/upload_document/", files={"file": BAD_EXTENSION})

    assert response.status_code == 400
    # ErrorDetail forbids unknown keys: a route that starts answering with a
    # filename or a parser message fails here rather than at a client.
    ErrorDetail(**response.json()["detail"])


def test_an_oversized_batch_answers_a_body_the_schema_describes(client):
    files = [("files", TXT) for _ in range(MAX_BATCH_FILES + 1)]

    response = client.post("/api/upload_documents/", files=files)

    assert response.status_code == 413
    ErrorDetail(**response.json()["detail"])
