# pylint: disable=W0621
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.extractions import router
from app.core.dependencies import get_entity_extractor, get_text_repository
from app.interfaces.repositories_interfaces import TextRepositoryInterface
from app.interfaces.service_interfaces import EntityExtractionServiceInterface
from app.schemas.extraction import EntityDetail


@pytest.fixture
def stored_entities():
    return {
        "pathologies": [
            EntityDetail(text="grippe", label="pathologie", score=0.95),
        ],
        "symptoms": [],
    }


@pytest.fixture
def mock_repository(stored_entities):
    repository = MagicMock(spec=TextRepositoryInterface)
    repository.get_entities = AsyncMock(return_value=stored_entities)
    repository.get_text = AsyncMock(return_value=None)
    repository.get_document_ttl = AsyncMock(return_value=1800)
    return repository


@pytest.fixture
def mock_entity_extractor():
    extractor = MagicMock(spec=EntityExtractionServiceInterface)
    extractor.get_mapping_info.return_value = {"language": "fr", "dataset": "cas"}
    return extractor


@pytest.fixture
def client(mock_repository, mock_entity_extractor):
    # Mount the router alone: app.main pulls in the NER stack, which this
    # endpoint no longer touches.
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_text_repository] = lambda: mock_repository
    app.dependency_overrides[get_entity_extractor] = lambda: mock_entity_extractor
    return TestClient(app)


def test_returns_the_stored_entities(client):
    file_id = uuid4()

    response = client.get(f"/api/get_extracted_text/{file_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["file_id"] == str(file_id)
    assert body["extracted_entities"]["pathologies"][0]["text"] == "grippe"
    assert body["expires_in_seconds"] == 1800
    assert body["mapping_info"] == {"language": "fr", "dataset": "cas"}


def test_never_runs_the_model_again(client, mock_entity_extractor):
    client.get(f"/api/get_extracted_text/{uuid4()}")

    # Entities are extracted once, at upload.
    mock_entity_extractor.extract_entities.assert_not_called()


def test_answers_without_text_when_it_was_not_stored(client):
    body = client.get(f"/api/get_extracted_text/{uuid4()}").json()

    assert body["text"] is None
    assert body["extracted_entities"]["pathologies"][0]["start"] is None


def test_returns_the_text_when_the_deployment_kept_it(client, mock_repository):
    mock_repository.get_text.return_value = "Le patient a la grippe."

    body = client.get(f"/api/get_extracted_text/{uuid4()}").json()

    assert body["text"] == "Le patient a la grippe."


def test_missing_document_is_not_found(client, mock_repository):
    mock_repository.get_entities.return_value = None

    response = client.get(f"/api/get_extracted_text/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"]["message"] == (
        "File not found or not processed yet."
    )


def test_a_document_without_entities_is_still_found(client, mock_repository):
    # An empty result means the model found nothing, not that the document is gone.
    mock_repository.get_entities.return_value = {}

    response = client.get(f"/api/get_extracted_text/{uuid4()}")

    assert response.status_code == 200


def test_rejects_a_malformed_id(client, mock_repository):
    response = client.get("/api/get_extracted_text/not-a-uuid")

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == (
        "Invalid file ID format. Expected UUID."
    )
    mock_repository.get_entities.assert_not_called()
