"""What the application mounts, and what it says when something escapes."""

# pylint: disable=W0621
import pytest

from fastapi import APIRouter
from fastapi.testclient import TestClient

from app import main
from app.main import DEVELOPMENT, PRODUCTION, create_app

MOCK_PATH = "/mock_summary"

# The stored-document endpoints this service used to serve. Kept as a fixed
# list so a future change that reintroduces one of them - even under a
# router mounted for another reason - fails a test rather than shipping
# silently: this service stores nothing, and mounting any of these again is a
# decision entry before it is code.
REMOVED_STORED_DOCUMENT_ENDPOINTS = {
    "/api/upload_document/",
    "/api/upload_documents/",
    "/api/get_extracted_text/{file_id}",
    "/api/documents/{file_id}",
}

# The development mock mirrored the extraction endpoint. It went with the route
# it mocked, and a mock answering a shape the API no longer sends is worse than
# no mock at all - so it is pinned against the development app, where mocks do
# mount.
REMOVED_MOCK_PATH = "/mock_extracted_text/{file_id}"


def paths(app):
    return {route.path for route in app.routes}


def test_production_does_not_mount_the_development_endpoints():
    assert MOCK_PATH not in paths(create_app(PRODUCTION))


def test_neither_environment_mounts_a_stored_document_endpoint():
    for environment in (PRODUCTION, DEVELOPMENT):
        assert not REMOVED_STORED_DOCUMENT_ENDPOINTS & paths(create_app(environment))


def test_development_does_not_mount_the_removed_extraction_mock():
    assert REMOVED_MOCK_PATH not in paths(create_app(DEVELOPMENT))


def test_a_stored_document_request_answers_not_found(monkeypatch):
    # The model is never involved in routing a 404, but building the real
    # application still loads it at startup - stubbed here the same way the
    # other TestClient-backed tests in this module stub it.
    monkeypatch.setattr(main, "get_entity_extractor", lambda: object())

    with TestClient(create_app(PRODUCTION)) as client:
        file_id = "123e4567-e89b-12d3-a456-426614174000"

        assert client.post("/api/upload_document/").status_code == 404
        assert client.post("/api/upload_documents/").status_code == 404
        assert client.get(f"/api/get_extracted_text/{file_id}").status_code == 404
        assert client.delete(f"/api/documents/{file_id}").status_code == 404


def test_development_mounts_them_when_asked_explicitly():
    assert MOCK_PATH in paths(create_app(DEVELOPMENT))


def test_an_unset_environment_builds_the_production_application(monkeypatch):
    monkeypatch.delenv("APP_ENV", raising=False)

    assert MOCK_PATH not in paths(create_app())


def test_the_environment_decides_when_nothing_is_passed(monkeypatch):
    monkeypatch.setenv("APP_ENV", DEVELOPMENT)

    assert MOCK_PATH in paths(create_app())


def test_the_model_is_read_at_startup_not_by_the_first_caller(monkeypatch):
    # Lazily loaded, the weights were read inside the first analysis, which paid
    # seconds of CPU for a cost that belongs to the process.
    loads = []
    monkeypatch.setattr(main, "get_entity_extractor", lambda: loads.append(1))

    with TestClient(create_app(PRODUCTION)) as client:
        assert loads == [1]
        assert client.get("/readyz").status_code == 200


def test_a_model_that_will_not_load_leaves_the_service_up_and_unready(monkeypatch):
    def refuse_to_load():
        raise OSError("no model at /app/models")

    monkeypatch.setattr(main, "get_entity_extractor", refuse_to_load)

    with TestClient(create_app(PRODUCTION)) as client:
        # Up, and honest about it: a crash loop says nothing about why.
        assert client.get("/healthz").status_code == 200
        assert client.get("/readyz").status_code == 503


def test_a_failed_load_logs_a_type_and_never_the_path(monkeypatch, caplog):
    def refuse_to_load():
        # A model path is deployment configuration, and the exceptions raised
        # around a document quote the value they choked on.
        raise OSError("no model at /home/jeanne-dupont/models")

    monkeypatch.setattr(main, "get_entity_extractor", refuse_to_load)

    with TestClient(create_app(PRODUCTION)):
        pass

    assert "OSError" in caplog.text
    assert "jeanne-dupont" not in caplog.text


@pytest.fixture
def failing_client():
    """An application with one route that raises something nobody handled."""
    app = create_app(PRODUCTION)
    router = APIRouter()

    @router.get("/boom")
    async def boom():
        raise RuntimeError("Jeanne Dupont, née le 3 mars 1970")

    app.include_router(router)
    # Let the handler answer instead of re-raising into the test.
    return TestClient(app, raise_server_exceptions=False)


def test_an_unhandled_error_answers_a_fixed_body(failing_client):
    response = failing_client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {"detail": {"message": "Internal server error"}}


def test_an_unhandled_error_logs_a_name_and_never_the_message(failing_client, caplog):
    failing_client.get("/boom")

    assert "RuntimeError" in caplog.text
    # The message of an exception raised near a parsed document is document
    # content, and a traceback carries the values in scope with it.
    assert "Jeanne" not in caplog.text
    assert "Traceback" not in caplog.text
