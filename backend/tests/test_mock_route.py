"""A mock that answers a shape the real API never sends is worse than none.

These assertions are what makes it a mock rather than a plausible-looking
fixture, so the payload is validated against the real response model.
"""

# pylint: disable=W0621
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.mock import MOCK_ENTITIES, MOCK_TEXT, mock_router
from app.schemas.extraction import (
    AnalysisResponse,
    ExtractedEntities,
    ExtractionResponse,
)

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


def test_every_mocked_offset_indexes_its_own_text():
    # The mock's whole claim is that it answers what the real API answers. An
    # offset that no longer lands on its entity makes it a plausible fixture.
    for details in MOCK_ENTITIES.values():
        for entity in details:
            assert MOCK_TEXT[entity.start : entity.end] == entity.text


class TestMockSummary:
    @pytest.fixture
    def summary_payload(self, client):
        response = client.get("/mock_summary")
        assert response.status_code == 200
        return response.json()

    def test_the_mock_answers_the_real_response_model(self, summary_payload):
        AnalysisResponse(**summary_payload)

    def test_it_carries_a_readable_summary(self, summary_payload):
        summary = summary_payload["summary"]

        assert summary["patient"] == "Patient, 67 ans."
        assert summary["empty"] is False
        sections = {section["key"]: section for section in summary["sections"]}
        assert sections["pathologies"]["sentence"] == "Grippe."

    def test_it_never_echoes_the_document_text(self, summary_payload):
        assert "text" not in summary_payload

    def test_it_can_pretend_several_documents_were_merged(self, client):
        payload = client.get("/mock_summary?documents=3").json()

        assert payload["summary"]["document_count"] == 3
        assert len(payload["documents"]) == 3
        # The same finding in three documents is still reported once.
        sections = {s["key"]: s for s in payload["summary"]["sections"]}
        assert sections["pathologies"]["findings"] == ["grippe"]

    def test_it_refuses_more_documents_than_the_real_endpoint_takes(self, client):
        assert client.get("/mock_summary?documents=21").status_code == 422
