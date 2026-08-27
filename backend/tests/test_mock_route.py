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
        assert sections["pathologies"]["findings"] == [
            {"text": "grippe", "documents": [0, 1, 2]}
        ]

    def test_it_refuses_more_documents_than_the_real_endpoint_takes(self, client):
        assert client.get("/mock_summary?documents=21").status_code == 422

    def test_it_can_pretend_one_document_could_not_be_read(self, client):
        payload = client.get("/mock_summary?documents=3&unreadable=1").json()

        assert [document["read"] for document in payload["documents"]] == [
            True,
            True,
            False,
        ]
        assert payload["documents"][2]["unreadable_reason"] == "no_text"
        assert payload["summary"]["document_count"] == 2

    def test_it_never_pretends_the_whole_batch_failed(self, client):
        # That answer is a 400 on the real route, so the mock cannot serve it
        # as a summary without teaching the client a shape that never arrives.
        payload = client.get("/mock_summary?documents=2&unreadable=5").json()

        assert [document["read"] for document in payload["documents"]] == [True, False]
        assert payload["summary"]["document_count"] == 1

    def test_asking_for_every_document_unreadable_still_keeps_one(self, client):
        # `unreadable` equal to `documents` is the same request the endpoint's
        # own docstring calls out: capped at one below `documents`, since a
        # batch nothing could be read from is a 400 on the real route, not a
        # summary the mock could serve.
        payload = client.get("/mock_summary?documents=3&unreadable=3").json()

        assert [document["read"] for document in payload["documents"]] == [
            True,
            False,
            False,
        ]
        assert payload["summary"]["document_count"] == 1
        assert len(payload["documents"]) == 3

    def test_it_dates_every_document_it_pretends_was_read(self, client):
        payload = client.get("/mock_summary?documents=3&unreadable=1").json()

        dates = [document["document_date"] for document in payload["documents"]]
        # A week apart, so the client sees a range rather than one date three
        # times, and nothing at all for the document it could not read.
        assert dates == ["2024-03-04", "2024-03-11", None]
        assert payload["summary"]["date_range"] == {
            "start": "2024-03-04",
            "end": "2024-03-11",
        }

    def test_dates_stay_aligned_with_read_when_unreadable_is_capped(self, client):
        # `unreadable=documents` is capped to `documents - 1` before either
        # list is built. The date list and the read/unread list must be capped
        # the same way, or a date would end up reported against a document the
        # payload also marks unread.
        payload = client.get("/mock_summary?documents=3&unreadable=3").json()

        read = [document["read"] for document in payload["documents"]]
        dates = [document["document_date"] for document in payload["documents"]]
        assert read == [True, False, False]
        assert dates == ["2024-03-04", None, None]

    def test_it_pairs_a_value_with_the_examination_it_sits_beside(self, client):
        summary = client.get("/mock_summary").json()["summary"]

        sections = {section["key"]: section for section in summary["sections"]}
        assert sections["examinations"]["findings"] == [
            {"text": "Troponine I 1,10 ng/mL", "documents": [0]}
        ]
