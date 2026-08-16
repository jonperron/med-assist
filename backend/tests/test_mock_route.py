"""A mock that answers a shape the real API never sends is worse than none.

These assertions are what makes it a mock rather than a plausible-looking
fixture, so the payload is validated against the real response model.
"""

# pylint: disable=W0621
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.mock import MOCK_TEXT, mock_router
from app.schemas.extraction import ExtractedEntities, ExtractionResponse

FILE_ID = "123e4567-e89b-12d3-a456-426614174000"


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(mock_router)
    return TestClient(app)


@pytest.fixture
def payload(client):
    response = client.get(f"/mock_extracted_text/{FILE_ID}")
    assert response.status_code == 200
    return response.json()


def test_the_mock_answers_the_real_response_model(payload):
    # Validating with the production model is the point: a field the API does
    # not have, or a category holding plain strings, fails right here.
    ExtractionResponse(**payload)

    assert payload["file_id"] == FILE_ID
    assert payload["extracted_entities"]["pathologies"][0]["text"] == "grippe"


def test_the_default_answer_is_the_one_the_shipped_configuration_gives(payload):
    # STORE_DOCUMENT_TEXT is off by default, so the real endpoint answers
    # without the text and without offsets - the branch the viewer renders.
    assert payload["text"] is None
    for details in payload["extracted_entities"].values():
        for entity in details:
            assert entity["start"] is None
            assert entity["end"] is None


def test_the_retained_answer_carries_the_text_and_its_offsets(client):
    payload = client.get(f"/mock_extracted_text/{FILE_ID}?retained=true").json()

    assert payload["text"] == MOCK_TEXT
    for details in payload["extracted_entities"].values():
        for entity in details:
            assert MOCK_TEXT[entity["start"] : entity["end"]] == entity["text"]


def test_the_mocked_categories_exist_on_the_real_model(payload):
    assert set(payload["extracted_entities"]) <= set(ExtractedEntities.model_fields)


def test_a_malformed_id_is_refused_as_the_real_routes_refuse_it(client):
    response = client.get("/mock_extracted_text/not-a-uuid")

    assert response.status_code == 400
    assert (
        response.json()["detail"]["message"] == "Invalid file ID format. Expected UUID."
    )
