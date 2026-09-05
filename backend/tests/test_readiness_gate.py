"""A model that will not load must refuse work, not retry itself into the ground.

`lru_cache` does not memoise an exception, so before the gate every request that
arrived after a failed startup load began the whole multi-second load again, in
a worker thread, and there was no request count at which that stopped.
"""

# pylint: disable=W0621
import pytest

from fastapi.testclient import TestClient

from app import main
from app.core.readiness import MODEL_NOT_LOADED
from app.main import PRODUCTION, create_app

TXT_FILE = ("note.txt", b"Le patient a de la fievre", "text/plain")


@pytest.fixture
def loads():
    """Every attempt to build the extractor, whoever made it."""
    return []


@pytest.fixture
def client(monkeypatch, loads):
    def refuse_to_load():
        loads.append(1)
        raise OSError("no model here")

    monkeypatch.setattr(main, "get_entity_extractor", refuse_to_load)
    # Credentialed: the readiness refusal is what these tests pin, and an
    # anonymous caller would be refused by the credential gate before the
    # readiness dependency ever ran.
    with TestClient(create_app(PRODUCTION)) as test_client:
        yield test_client


def test_analysis_is_refused_while_the_model_is_missing(client):
    response = client.post("/api/analyze", files={"file": TXT_FILE})

    assert response.status_code == 503
    assert response.json() == {"detail": {"message": MODEL_NOT_LOADED}}


def test_the_streaming_route_refuses_the_same_way(client):
    # The two analysis endpoints share the gate, so they must share the answer.
    response = client.post("/api/analyze/stream", files={"file": TXT_FILE})

    assert response.status_code == 503


def test_a_refused_request_does_not_try_to_load_the_model_again(client, loads):
    for _ in range(3):
        client.post("/api/analyze", files={"file": TXT_FILE})

    # One attempt, at startup. The requests cost a refusal each, not a load.
    assert loads == [1]
