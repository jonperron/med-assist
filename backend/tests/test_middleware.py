# pylint: disable=W0621

import json

import pytest
from fastapi import FastAPI, Request, UploadFile
from fastapi.testclient import TestClient

from app.core.middleware import (
    MAX_REQUEST_SIZE_BYTES,
    REQUEST_TOO_LARGE,
    LimitRequestSize,
    forbid_caching,
)


@pytest.fixture
def client():
    # Same order as app.main: forbid_caching is registered last so it wraps the
    # size refusal too.
    app = FastAPI()
    app.add_middleware(LimitRequestSize)
    app.middleware("http")(forbid_caching)

    @app.post("/echo")
    async def echo(request: Request):  # pylint: disable=W0612
        body = await request.body()
        return {"received_bytes": len(body)}

    # The shape the analysis routes actually take. It is tested separately
    # because FastAPI reports a multipart body that stops early as its own 400,
    # so a limit that only works on a plain body reads as passing here and
    # answers the wrong status on the one path that spools to disk.
    @app.post("/upload")
    async def upload(files: list[UploadFile]):  # pylint: disable=W0612
        return {"received_bytes": sum(file.size or 0 for file in files)}

    return TestClient(app)


def chunked(body: bytes):
    """
    Send a body with no Content-Length.

    httpx uses Transfer-Encoding: chunked for an iterator body, which is what a
    client streaming an upload does - and what the declared-length check cannot
    see.
    """
    return iter([body])


def multipart(payload: bytes) -> tuple[bytes, dict]:
    """Wrap a payload as a one-file multipart body, built by hand so it can be
    sent without a declared length."""
    body = (
        b'--B\r\nContent-Disposition: form-data; name="files"; '
        b'filename="d.txt"\r\nContent-Type: text/plain\r\n\r\n'
        + payload
        + b"\r\n--B--\r\n"
    )
    return body, {"Content-Type": "multipart/form-data; boundary=B"}


def test_accepts_a_body_within_the_ceiling(client):
    response = client.post("/echo", content=b"x" * 1024)

    assert response.status_code == 200


def test_accepts_a_request_with_no_body_at_all(client):
    response = client.post("/echo")

    assert response.status_code == 200
    assert response.json()["received_bytes"] == 0


def test_refuses_a_body_over_the_declared_ceiling(client):
    # The body is never sent: only the declared length is needed to refuse it.
    response = client.post(
        "/echo",
        content=b"x",
        headers={"content-length": str(MAX_REQUEST_SIZE_BYTES + 1)},
    )

    assert response.status_code == 413
    assert response.json()["detail"]["message"] == REQUEST_TOO_LARGE


def test_ignores_a_malformed_content_length(client):
    response = client.post("/echo", headers={"content-length": "not-a-number"})

    assert response.status_code != 413


def test_refuses_an_undeclared_body_over_the_ceiling(client):
    # The regression this middleware exists for: a chunked body declares no
    # length, so nothing stopped it reaching the multipart spool in full.
    response = client.post(
        "/echo", content=chunked(b"x" * (MAX_REQUEST_SIZE_BYTES + 1))
    )

    assert response.status_code == 413
    assert response.json()["detail"]["message"] == REQUEST_TOO_LARGE


def test_accepts_an_undeclared_body_within_the_ceiling(client):
    payload = b"x" * 4096
    response = client.post("/echo", content=chunked(payload))

    assert response.status_code == 200
    assert response.json()["received_bytes"] == len(payload)


def test_accepts_a_declared_body_of_exactly_the_ceiling(client):
    # The boundary the declared-length check draws the line at: equal to the
    # ceiling is accepted, and only a body one byte over it is refused.
    payload = b"x" * MAX_REQUEST_SIZE_BYTES
    response = client.post(
        "/echo",
        content=payload,
        headers={"content-length": str(MAX_REQUEST_SIZE_BYTES)},
    )

    assert response.status_code == 200
    assert response.json()["received_bytes"] == MAX_REQUEST_SIZE_BYTES


def test_accepts_an_undeclared_body_of_exactly_the_ceiling(client):
    # Same boundary on the receive-channel counter that guards a chunked body:
    # exactly the ceiling passes, one byte more (already covered above) does not.
    payload = b"x" * MAX_REQUEST_SIZE_BYTES
    response = client.post("/echo", content=chunked(payload))

    assert response.status_code == 200
    assert response.json()["received_bytes"] == MAX_REQUEST_SIZE_BYTES


def test_the_refusal_reports_the_ceiling_not_the_body(client):
    response = client.post(
        "/echo", content=chunked(b"x" * (MAX_REQUEST_SIZE_BYTES + 1))
    )

    detail = response.json()["detail"]
    assert detail["max_size_bytes"] == MAX_REQUEST_SIZE_BYTES
    # A received size would be a measurement of the caller's documents. The
    # declared-length branch may report one; this branch has no complete figure
    # to report and must not invent one.
    assert "received_size_bytes" not in detail


def test_refuses_an_undeclared_multipart_body_over_the_ceiling(client):
    # The path that matters: an upload with no declared length, on the body
    # shape that gets spooled to TMPDIR. FastAPI turns the truncated parse into
    # a 400 of its own, which the middleware has to replace.
    body, headers = multipart(b"x" * (MAX_REQUEST_SIZE_BYTES + 1))
    response = client.post("/upload", content=chunked(body), headers=headers)

    assert response.status_code == 413
    assert response.json()["detail"]["message"] == REQUEST_TOO_LARGE


def test_accepts_an_undeclared_multipart_body_within_the_ceiling(client):
    payload = b"x" * (2 * 1024 * 1024)  # over the 1MB spool threshold
    body, headers = multipart(payload)
    response = client.post("/upload", content=chunked(body), headers=headers)

    assert response.status_code == 200
    assert response.json()["received_bytes"] == len(payload)


class TestTheCeilingStopsTheRead:
    """
    The property the middleware exists for, asserted directly.

    Every test above sends its body as a single message, so they prove the
    status code and nothing about when the middleware stopped reading. The
    point of the change is that the bytes never reach the spool - a 413 that
    arrives after the whole body was written would pass all of them.
    """

    @staticmethod
    def scope() -> dict:
        return {"type": "http", "headers": []}

    @pytest.mark.asyncio
    async def test_it_stops_pulling_once_the_ceiling_is_crossed(self):
        chunk = b"x" * 1024
        pulled = 0

        async def receive():
            nonlocal pulled
            pulled += 1
            return {"type": "http.request", "body": chunk, "more_body": True}

        async def app(scope, receive, send):
            while (await receive()).get("more_body"):
                pass

        sent: list = []

        async def send(message):
            sent.append(message)

        # Four chunks fit exactly; the fifth crosses and must be the last read.
        await LimitRequestSize(app, max_bytes=4096)(self.scope(), receive, send)

        assert pulled == 5
        assert sent[0]["status"] == 413

    @pytest.mark.asyncio
    async def test_the_refusal_reports_the_injected_ceiling(self):
        async def receive():
            return {"type": "http.request", "body": b"x" * 100, "more_body": True}

        async def app(scope, receive, send):
            while (await receive()).get("more_body"):
                pass

        sent: list = []

        async def send(message):
            sent.append(message)

        await LimitRequestSize(app, max_bytes=10)(self.scope(), receive, send)

        body = json.loads(sent[1]["body"])
        # Not MAX_REQUEST_SIZE_BYTES: the ceiling enforced is the one reported.
        assert body["detail"]["max_size_bytes"] == 10
        assert body["detail"]["max_size_bytes"] != MAX_REQUEST_SIZE_BYTES


def test_responses_are_never_cached(client):
    response = client.post("/echo", content=b"x")

    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"


def test_a_declared_refusal_is_also_uncacheable(client):
    response = client.post(
        "/echo", headers={"content-length": str(MAX_REQUEST_SIZE_BYTES + 1)}
    )

    assert response.headers["cache-control"] == "no-store"


def test_an_undeclared_refusal_is_also_uncacheable(client):
    response = client.post(
        "/echo", content=chunked(b"x" * (MAX_REQUEST_SIZE_BYTES + 1))
    )

    assert response.headers["cache-control"] == "no-store"
