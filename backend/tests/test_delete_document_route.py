# pylint: disable=W0621
import pytest
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.uploads import router
from app.core.dependencies import get_text_repository
from app.interfaces.repositories_interfaces import TextRepositoryInterface


@pytest.fixture
def mock_repository():
    repository = MagicMock(spec=TextRepositoryInterface)
    repository.delete_text = AsyncMock(return_value=True)
    return repository


@pytest.fixture
def client(mock_repository):
    # Mount the router alone: app.main pulls in the NER stack, which this
    # endpoint does not touch.
    app = FastAPI()
    app.include_router(router, prefix="/api")
    app.dependency_overrides[get_text_repository] = lambda: mock_repository
    return TestClient(app)


def test_delete_document(client, mock_repository):
    file_id = uuid4()

    response = client.delete(f"/api/documents/{file_id}")

    assert response.status_code == 204
    mock_repository.delete_text.assert_called_once_with(file_id)


def test_delete_document_not_found(client, mock_repository):
    mock_repository.delete_text.return_value = False

    response = client.delete(f"/api/documents/{uuid4()}")

    assert response.status_code == 404
    assert response.json()["detail"]["message"] == (
        "Document not found or already expired."
    )


def test_delete_document_rejects_malformed_id(client, mock_repository):
    response = client.delete("/api/documents/not-a-uuid")

    assert response.status_code == 400
    assert response.json()["detail"]["message"] == (
        "Invalid file ID format. Expected UUID."
    )
    mock_repository.delete_text.assert_not_called()
