"""What the application mounts, and what it says when something escapes."""

# pylint: disable=W0621
import pytest

from fastapi import APIRouter
from fastapi.testclient import TestClient

from app import main
from app.main import DEVELOPMENT, PRODUCTION, create_app

MOCK_PATH = "/mock_extracted_text/{file_id}"


def paths(app):
    return {route.path for route in app.routes}


def test_production_does_not_mount_the_development_endpoints():
    assert MOCK_PATH not in paths(create_app(PRODUCTION))


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
