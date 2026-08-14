# pylint: disable=W0621
import pytest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.middleware import (
    MAX_REQUEST_SIZE_BYTES,
    forbid_caching,
    reject_oversized_requests,
)


@pytest.fixture
def client():
    # Same order as app.main: forbid_caching is registered last so it wraps the
    # size refusal too.
    app = FastAPI()
    app.middleware("http")(reject_oversized_requests)
    app.middleware("http")(forbid_caching)

    @app.post("/echo")
    async def echo():  # pylint: disable=W0612
        return {"ok": True}

    return TestClient(app)


def test_accepts_a_body_within_the_ceiling(client):
    response = client.post("/echo", content=b"x" * 1024)

    assert response.status_code == 200


def test_refuses_a_body_over_the_ceiling(client):
    # The body is never sent: only the declared length is needed to refuse it.
    response = client.post(
        "/echo",
        content=b"x",
        headers={"content-length": str(MAX_REQUEST_SIZE_BYTES + 1)},
    )

    assert response.status_code == 413
    assert response.json()["detail"]["message"] == "Request too large"


def test_ignores_a_malformed_content_length(client):
    response = client.post("/echo", headers={"content-length": "not-a-number"})

    assert response.status_code != 413


def test_responses_are_never_cached(client):
    response = client.post("/echo", content=b"x")

    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"


def test_a_refusal_is_also_uncacheable(client):
    response = client.post(
        "/echo", headers={"content-length": str(MAX_REQUEST_SIZE_BYTES + 1)}
    )

    assert response.headers["cache-control"] == "no-store"
