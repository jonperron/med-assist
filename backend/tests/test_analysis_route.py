# pylint: disable=W0621
import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.analysis import router
from app.core.config import PrivacyConfiguration
from app.core.dependencies import (
    get_entity_extractor,
    get_privacy_config,
    get_pseudonymizer,
    get_text_extractor,
)
from app.interfaces.service_interfaces import (
    EntityExtractionServiceInterface,
    TextExtractionServiceInterface,
)
from app.schemas.extraction import EntityDetail
from app.services.pseudonymizer import Pseudonymizer

TEXT = "Le homme a de la fièvre"
TXT_FILE = ("note.txt", b"Le homme a de la fievre", "text/plain")


@pytest.fixture
def mock_text_extractor():
    mock = MagicMock(spec=TextExtractionServiceInterface)
    mock.extract_text = AsyncMock(return_value=TEXT)
    return mock


@pytest.fixture
def mock_entity_extractor():
    mock = MagicMock(spec=EntityExtractionServiceInterface)
    mock.extract_entities.return_value = {
        "patient_info": [
            EntityDetail(text="homme", label="genre", score=0.9, start=3, end=8)
        ],
        "symptoms": [
            EntityDetail(text="fièvre", label="sosy", score=0.8, start=17, end=23)
        ],
    }
    mock.get_mapping_info.return_value = {"language": "fr", "dataset": "cas"}
    return mock


@pytest.fixture
def privacy_config():
    return PrivacyConfiguration(STORE_DOCUMENT_TEXT=False, PSEUDONYMIZE_ENTITIES=False)


@pytest.fixture
def client(mock_text_extractor, mock_entity_extractor, privacy_config):
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_text_extractor] = lambda: mock_text_extractor
    app.dependency_overrides[get_entity_extractor] = lambda: mock_entity_extractor
    # A lambda, not the class: FastAPI would read the constructor signature and
    # try to resolve the detector as a request field.
    app.dependency_overrides[get_pseudonymizer] = lambda: Pseudonymizer()
    app.dependency_overrides[get_privacy_config] = lambda: privacy_config
    return TestClient(app)


def test_analyze_returns_entities(client):
    response = client.post("/api/analyze", files={"file": TXT_FILE})

    assert response.status_code == 200
    body = response.json()
    assert body["extracted_entities"]["symptoms"][0]["text"] == "fièvre"
    assert body["mapping_info"] == {"language": "fr", "dataset": "cas"}


def test_analyze_never_stores_anything(client):
    response = client.post("/api/analyze", files={"file": TXT_FILE})

    body = response.json()
    assert body["retained"] is False
    # Nothing to come back for: no identifier is issued.
    assert "file_id" not in body
    assert "expires_in_seconds" not in body


def test_analyze_does_not_mask_when_the_deployment_turned_it_off(client):
    body = client.post("/api/analyze", files={"file": TXT_FILE}).json()

    assert body["pseudonymized"] is False
    assert body["text"] == TEXT


def test_a_request_cannot_turn_off_the_deployment_policy(client, privacy_config):
    privacy_config.pseudonymize = True

    body = client.post(
        "/api/analyze", files={"file": TXT_FILE}, data={"pseudonymize": "false"}
    ).json()

    assert body["pseudonymized"] is True
    assert "homme" not in body["text"]


def test_analyze_masks_patient_info_on_request(client):
    body = client.post(
        "/api/analyze", files={"file": TXT_FILE}, data={"pseudonymize": "true"}
    ).json()

    assert body["pseudonymized"] is True
    assert "homme" not in body["text"]
    assert "[GENRE_1]" in body["text"]
    assert body["extracted_entities"]["symptoms"][0]["text"] == "fièvre"


def test_analyze_follows_the_configured_default(client, privacy_config):  # pylint: disable=W0613
    privacy_config.pseudonymize = True

    body = client.post("/api/analyze", files={"file": TXT_FILE}).json()

    assert body["pseudonymized"] is True
    assert "homme" not in body["text"]


def test_analyze_rejects_an_unsupported_file_type(client):
    response = client.post(
        "/api/analyze", files={"file": ("note.exe", b"binary", "application/exe")}
    )

    assert response.status_code == 400


def test_analyze_reports_an_empty_document(client, mock_text_extractor):
    mock_text_extractor.extract_text = AsyncMock(return_value="")

    response = client.post("/api/analyze", files={"file": TXT_FILE})

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == (
        "Unable to extract text from the document."
    )


def test_analyze_hides_internal_failures(client, mock_entity_extractor, caplog):
    mock_entity_extractor.extract_entities.side_effect = RuntimeError(
        "model crashed on 'Le homme a de la fièvre'"
    )

    response = client.post("/api/analyze", files={"file": TXT_FILE})

    assert response.status_code == 500
    assert response.json()["detail"] == {"message": "Internal server error"}
    # Neither the document content nor the filename reaches the log.
    assert "homme" not in caplog.text
    assert "note.txt" not in caplog.text
