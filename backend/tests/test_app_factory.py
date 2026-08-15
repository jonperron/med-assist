"""What the application mounts, and what it says when something escapes."""

# pylint: disable=W0621
import pytest

from fastapi import APIRouter
from fastapi.testclient import TestClient

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
