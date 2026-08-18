"""Liveness answers for the process, readiness answers for the model.

The model loads in seconds on a CPU, and until it is in memory the service can
hold a connection without being able to analyse anything. These tests hold the
two answers apart.
"""

# pylint: disable=W0621
import pytest

from fastapi.testclient import TestClient

from app.core.readiness import MODEL_NOT_LOADED
from app.main import PRODUCTION, create_app


@pytest.fixture
def app():
    return create_app(PRODUCTION)


@pytest.fixture
def client(app):
    # Not entered as a context manager: the lifespan handler stays out of it, so
    # each case sets the state it wants to describe.
    return TestClient(app)


def test_liveness_does_not_depend_on_the_model(app, client):
    app.state.model_loaded = False

    assert client.get("/healthz").status_code == 200


def test_readiness_refuses_until_the_model_is_loaded(app, client):
    app.state.model_loaded = False

    response = client.get("/readyz")

    assert response.status_code == 503
    # The same envelope every other refusal uses, so a client reads one shape.
    assert response.json() == {"detail": {"message": MODEL_NOT_LOADED}}


def test_readiness_answers_once_the_model_is_loaded(app, client):
    app.state.model_loaded = True

    response = client.get("/readyz")

    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


def test_readiness_says_nothing_about_the_deployment(app, client):
    # A readiness body is reachable from wherever the port is. It carries a
    # fixed string and no path, model name, or reason.
    app.state.model_loaded = False

    body = client.get("/readyz").text

    assert "model" not in body.lower()
    assert "/" not in body


def test_an_application_that_never_declared_itself_is_taken_as_ready(client):
    # A router mounted without the lifespan - a test, or an embedding that runs
    # its own startup - has claimed nothing, and the guard does not invent a
    # claim on its behalf.
    assert client.get("/readyz").status_code == 200
