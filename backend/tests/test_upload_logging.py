"""Clinical filenames routinely contain patient names, so they never get logged.

This rule decays silently, so it is asserted rather than documented.
"""

# pylint: disable=W0621
import logging

import pytest
from unittest.mock import AsyncMock, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.uploads import router
from app.core.dependencies import get_file_handler, get_text_repository
from app.interfaces.repositories_interfaces import TextRepositoryInterface
from app.services.file_handler import FileHandler

PATIENT_FILENAME = "compte-rendu-Jeanne-Dupont.txt"
FILE = (PATIENT_FILENAME, b"Le patient a de la fievre", "text/plain")


@pytest.fixture
def mock_file_handler():
    handler = MagicMock(spec=FileHandler)
    handler.process_file = AsyncMock(
        side_effect=RuntimeError(f"failed reading {PATIENT_FILENAME}: Jeanne Dupont")
    )
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


def test_single_upload_failure_never_logs_the_filename(client, caplog):
    with caplog.at_level(logging.ERROR):
        response = client.post("/api/upload_document/", files={"file": FILE})

    assert response.status_code == 500
    assert caplog.text, "the failure should still be logged"
    assert PATIENT_FILENAME not in caplog.text
    assert "Jeanne" not in caplog.text
    assert "RuntimeError" in caplog.text


def test_batch_upload_failure_never_logs_the_filename(client, caplog):
    with caplog.at_level(logging.ERROR):
        response = client.post("/api/upload_documents/", files={"files": FILE})

    assert response.status_code == 500
    assert caplog.text, "the failure should still be logged"
    assert PATIENT_FILENAME not in caplog.text
    assert "Jeanne" not in caplog.text
