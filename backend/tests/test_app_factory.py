"""What the application mounts, and what it says when something escapes."""

# pylint: disable=W0621
import logging

import pytest

from fastapi import APIRouter
from fastapi.testclient import TestClient

from app import main
from app.core.config import DEFAULT_ALLOWED_ORIGINS
from app.core.gate import covers
from app.core.origin import ORIGIN_VARIABLE
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

# Every path the application answers that is not behind `RequireKnownOrigin`.
# The gate covers a prefix, not a list of routes, so this set is deliberately
# closed: a route that belongs here is added to it by a reviewer, not
# discovered by a test failure in production.
OPEN_PATHS = {
    "/",
    "/openapi.json",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/healthz",
    "/readyz",
    MOCK_PATH,
}


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

    # A 404 rather than anything else: no gate answers ahead of the router on
    # these paths, so what is being pinned is that the route itself is gone.
    with TestClient(create_app(PRODUCTION)) as client:
        file_id = "123e4567-e89b-12d3-a456-426614174000"

        assert client.post("/api/upload_document/").status_code == 404
        assert client.post("/api/upload_documents/").status_code == 404
        assert client.get(f"/api/get_extracted_text/{file_id}").status_code == 404
        assert client.delete(f"/api/documents/{file_id}").status_code == 404


def test_every_route_answers_from_behind_the_origin_gate_or_the_open_list():
    """
    Every mounted path is either under `/api` or on a fixed, reviewed list.

    `RequireKnownOrigin` gates the `/api` prefix, not a table of routes, so an
    addition under that prefix is covered the moment it is registered -
    `test_origin_gate.py` exercises that. What no prefix-based gate can catch is
    the opposite mistake: a router included without `prefix="/api"`, which
    mounts ungated at whatever path it declares and nothing about the gate
    itself changes. This test would fail the day that happened, in either
    environment, rather than relying on whoever added the route to have also
    remembered to widen `OPEN_PATHS` or `test_everything_outside_the_api_prefix_is_open`
    by hand.

    The prefix is tested with the gate's own `covers` rather than a
    `startswith`, because the two do not agree: `/apiary` starts with `/api` and
    is not covered. A route mounted there would satisfy a `startswith` check
    while sitting outside `RequireKnownOrigin` - this test asserting the policy
    holds when it does not is worse than not having it.
    """
    for environment in (PRODUCTION, DEVELOPMENT):
        for path in paths(create_app(environment)):
            assert path in OPEN_PATHS or covers(
                path
            ), f"{path} in {environment} is neither under /api nor on the open list"


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


def test_startup_says_the_analysis_routes_authenticate_nobody(monkeypatch, caplog):
    """
    The operator-facing half of the honesty pair the banner covers on screen.

    At WARNING rather than INFO on purpose: uvicorn installs handlers on its own
    loggers only, so an `app.*` record below WARNING falls through to
    `logging.lastResort` and is dropped. A deployment that authenticates nobody
    should not have to configure logging to be told so.
    """
    monkeypatch.setattr(main, "get_entity_extractor", lambda: object())

    with caplog.at_level(logging.WARNING, logger="app.main"):
        with TestClient(create_app(PRODUCTION)):
            pass

    assert "authenticate nobody" in caplog.text
    assert ORIGIN_VARIABLE in caplog.text
    # The configured origins are the operator's own validated configuration, so
    # they are safe to name - and naming them is the point, since the 403 body
    # is fixed and the refusal log omits the origin it rejected.
    assert DEFAULT_ALLOWED_ORIGINS[0] in caplog.text


def test_a_retired_credential_still_in_the_environment_is_called_out(
    monkeypatch, caplog
):
    """
    An upgrade that leaves `API_ACCESS_TOKEN` set gets told it does nothing.

    Compose used to refuse to start without the variable, so its silence was a
    signal. Now the variable is simply not read, and a proxy rule injecting the
    header keeps working while enforcing nothing - a control that reads as
    protective and is not. This is the only thing that says so.
    """
    monkeypatch.setattr(main, "get_entity_extractor", lambda: object())
    monkeypatch.setenv(main.RETIRED_CREDENTIAL_VARIABLE, "left-over-from-an-upgrade")

    with caplog.at_level(logging.WARNING, logger="app.main"):
        with TestClient(create_app(PRODUCTION)):
            pass

    assert main.RETIRED_CREDENTIAL_VARIABLE in caplog.text
    assert "no longer read" in caplog.text
    # The stale value is still a secret somewhere. Naming the variable is the
    # whole job; quoting what it holds would put it in the container log.
    assert "left-over-from-an-upgrade" not in caplog.text


def test_nothing_is_said_when_no_retired_credential_is_configured(monkeypatch, caplog):
    monkeypatch.setattr(main, "get_entity_extractor", lambda: object())
    monkeypatch.delenv(main.RETIRED_CREDENTIAL_VARIABLE, raising=False)

    with caplog.at_level(logging.WARNING, logger="app.main"):
        with TestClient(create_app(PRODUCTION)):
            pass

    assert main.RETIRED_CREDENTIAL_VARIABLE not in caplog.text


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
