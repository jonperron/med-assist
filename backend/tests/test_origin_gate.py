"""
The origin gate in front of the analysis routes.

CORS decides what a browser may *read*. This gate decides what the server will
*act on*, which is the half that was missing: a cross-site `POST /api/analyze`
was sent, parsed and analysed, and only the answer was withheld from the page
that asked for it. What is pinned here is that such a request is now refused,
that it is refused before the body is read, and that the refusal cannot be used
to discover which origins a deployment serves.
"""

# pylint: disable=W0621

import json
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.config import DEFAULT_ALLOWED_ORIGINS
from app.core.dependencies import get_entity_extractor, get_text_extractor
from app.core.middleware import MAX_REQUEST_SIZE_BYTES
from app.core.origin import FORBIDDEN, ORIGIN_VARIABLE, RequireKnownOrigin
from app.interfaces.service_interfaces import (
    EntityExtractionServiceInterface,
    TextExtractionServiceInterface,
)
from app.main import PRODUCTION, create_app
from app.schemas.extraction import EntityDetail

ANALYZE = "/api/analyze"
STREAM = "/api/analyze/stream"

# The origin a default deployment serves, and one it does not. Neither is a
# real host: the second is a documentation domain reserved by RFC 2606 so that
# a test can name an attacker without naming anybody.
ALLOWED_ORIGIN = DEFAULT_ALLOWED_ORIGINS[0]
FOREIGN_ORIGIN = "https://attacker.example"


def stubbed(app: FastAPI) -> FastAPI:
    """
    Put stub extractors in place of the ones that would read the weights.

    Needed even by tests that never analyse anything: FastAPI solves a route's
    dependencies before it reports a malformed body, so a request that gets past
    both gates with no files still builds the real extractor - and that reads
    `NER_MODEL_NAME`, which no test environment sets.
    """
    text_extractor = MagicMock(spec=TextExtractionServiceInterface)
    text_extractor.extract_text = AsyncMock(return_value="Le homme de 67 ans")

    entity_extractor = MagicMock(spec=EntityExtractionServiceInterface)
    entity_extractor.extract_entities = AsyncMock(
        return_value={
            "patient_info": [
                EntityDetail(text="67 ans", label="age", score=0.9, start=12, end=18)
            ]
        }
    )
    entity_extractor.get_mapping_info.return_value = {"language": "fr"}

    app.dependency_overrides[get_text_extractor] = lambda: text_extractor
    app.dependency_overrides[get_entity_extractor] = lambda: entity_extractor
    return app


@pytest.fixture
def client():
    """The real application, with the extractors stubbed out."""
    return TestClient(stubbed(create_app(PRODUCTION)))


def txt():
    return ("files", ("note.txt", b"contenu", "text/plain"))


def stream_events(response):
    """The `data:` payloads of a finished SSE response, decoded, in order."""
    return [
        json.loads(line.removeprefix("data:").strip())
        for line in response.text.splitlines()
        if line.startswith("data:")
    ]


def extractor_of(client_under_test):
    return client_under_test.app.dependency_overrides[get_entity_extractor]()


# --- Which origins are allowed through ------------------------------------


@pytest.mark.parametrize("path", [ANALYZE, STREAM])
def test_a_foreign_origin_is_refused_on_both_analysis_routes(client, path):
    response = client.post(path, headers={"Origin": FOREIGN_ORIGIN})

    assert response.status_code == 403
    assert response.json() == {"detail": {"message": FORBIDDEN}}


def test_the_configured_origin_reaches_the_route(client):
    # 422 rather than 200: the body is missing. What matters is that the gate
    # was not what answered.
    response = client.post(ANALYZE, headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 422


def test_a_request_carrying_no_origin_reaches_the_route(client):
    # The documented deployment shape. A proxy forwarding a server-side call
    # sends no `Origin`, and so does every scripted caller; refusing those would
    # refuse the proxy this feature tells operators to put in front. Nothing on
    # this API gates them - there is no credential.
    assert client.post(ANALYZE).status_code == 422


def test_the_allow_list_is_the_configured_one_not_a_literal(monkeypatch):
    # The origin gate and CORS read the same variable, so that the advisory
    # control and the enforced one cannot drift apart.
    deployed = "https://med-assist.example.org"
    monkeypatch.setenv(ORIGIN_VARIABLE, deployed)
    client_under_test = TestClient(stubbed(create_app(PRODUCTION)))

    assert (
        client_under_test.post(ANALYZE, headers={"Origin": deployed}).status_code == 422
    )
    assert (
        client_under_test.post(ANALYZE, headers={"Origin": ALLOWED_ORIGIN}).status_code
        == 403
    )


def test_an_origin_normalised_at_startup_still_matches(monkeypatch):
    # `normalise_origin` rewrites a configured entry into the form a browser
    # sends. If it did not, an operator writing the implicit port would get a
    # list that matches nothing and a service that refuses its own frontend.
    monkeypatch.setenv(ORIGIN_VARIABLE, "https://Med-Assist.example.org:443/")
    client_under_test = TestClient(stubbed(create_app(PRODUCTION)))

    response = client_under_test.post(
        ANALYZE, headers={"Origin": "https://med-assist.example.org"}
    )

    assert response.status_code == 422


def test_a_null_origin_is_refused(client):
    # What a browser sends from a sandboxed iframe, a `data:` document, or a
    # redirected cross-origin request. No deployment can serve it.
    response = client.post(ANALYZE, headers={"Origin": "null"})

    assert response.status_code == 403


def test_an_origin_that_only_prefixes_an_allowed_one_is_refused(client):
    # The comparison is whole-value, not a prefix. `http://localhost:3000.evil`
    # is a different site that a careless `startswith` would admit.
    response = client.post(
        ANALYZE, headers={"Origin": f"{ALLOWED_ORIGIN}.evil.example"}
    )

    assert response.status_code == 403


# --- The browser's own account, when there is no Origin header ------------


@pytest.mark.parametrize("site", ["cross-site", "same-site", "CROSS-SITE"])
def test_a_browser_reporting_a_foreign_site_is_refused_without_an_origin(client, site):
    response = client.post(ANALYZE, headers={"Sec-Fetch-Site": site})

    assert response.status_code == 403


@pytest.mark.parametrize("site", ["same-origin", "none"])
def test_a_browser_reporting_its_own_site_reaches_the_route(client, site):
    assert client.post(ANALYZE, headers={"Sec-Fetch-Site": site}).status_code == 422


@pytest.mark.parametrize("site", ["same-origin", "SAME-ORIGIN", "none"])
def test_a_same_origin_request_is_accepted_whatever_the_allow_list_says(
    monkeypatch, site
):
    """
    The one-domain deployment works without the operator listing their origin.

    `deploy/caddy/Caddyfile.example` serves the interface and `/api` from one
    domain. A browser sends that domain as `Origin` on every POST, so before
    this the deployment refused its own interface unless someone had set
    `CORS_ALLOWED_ORIGINS` - a variable that shape never needed, because CORS
    does not apply to a same-origin call. `Sec-Fetch-Site` is a forbidden
    header name, so a page cannot forge it and accepting it costs nothing.
    """
    monkeypatch.setenv(ORIGIN_VARIABLE, "https://elsewhere.example")
    client_under_test = TestClient(stubbed(create_app(PRODUCTION)))

    response = client_under_test.post(
        ANALYZE,
        headers={"Origin": "https://med-assist.example.org", "Sec-Fetch-Site": site},
    )

    assert response.status_code == 422


def test_an_allowed_origin_wins_over_a_cross_site_report(client):
    # A frontend on its own host calling an API on another is `cross-site` and
    # entirely legitimate - it is the split-host deployment the allow-list
    # exists to describe. `Sec-Fetch-Site` is only consulted when there is no
    # `Origin` to judge, or this would refuse that deployment.
    response = client.post(
        ANALYZE,
        headers={"Origin": ALLOWED_ORIGIN, "Sec-Fetch-Site": "cross-site"},
    )

    assert response.status_code == 422


# --- Nothing is read from a refused request -------------------------------


@pytest.mark.parametrize("path", [ANALYZE, STREAM])
def test_a_foreign_batch_is_refused_without_being_analysed(client, path):
    response = client.post(path, files=[txt()], headers={"Origin": FOREIGN_ORIGIN})

    assert response.status_code == 403
    extractor_of(client).extract_entities.assert_not_called()


def test_the_stream_refusal_is_json_before_any_stream_opens(client):
    # A refusal is ordinary JSON, not an error event inside a stream that was
    # opened in order to carry it.
    response = client.post(STREAM, files=[txt()], headers={"Origin": FOREIGN_ORIGIN})

    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/json")
    assert stream_events(response) == []


def test_an_allowed_batch_is_analysed_as_before(client):
    response = client.post(ANALYZE, files=[txt()], headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 200
    assert "summary" in response.json()


# --- The refusal itself ---------------------------------------------------


def test_the_refusal_is_not_cached(client):
    response = client.post(ANALYZE, headers={"Origin": FOREIGN_ORIGIN})

    assert response.headers["cache-control"] == "no-store"


def test_the_refusal_does_not_carry_an_authenticate_header(client):
    # 403, not 401. This API authenticates nobody, so there is no credential to
    # challenge a caller for and nothing it could present to change the answer.
    response = client.post(ANALYZE, headers={"Origin": FOREIGN_ORIGIN})

    assert "www-authenticate" not in response.headers


def test_the_refused_origin_never_reaches_a_log_line(client, caplog):
    # It is attacker-controlled text. Writing it verbatim into a log file is how
    # a log viewer ends up rendering someone else's content.
    with caplog.at_level(logging.WARNING, logger="app.core.gate"):
        client.post(ANALYZE, headers={"Origin": FOREIGN_ORIGIN})

    assert FOREIGN_ORIGIN not in caplog.text
    assert ANALYZE in caplog.text


def test_only_the_first_origin_header_is_read():
    # Two `Origin` headers is a malformed request. Taking the first is what
    # every proxy in front of this process will have done; trying each in turn
    # would let a caller append an accepted value to a refused request.
    application = stubbed(create_app(PRODUCTION))
    client_under_test = TestClient(application)

    response = client_under_test.post(
        ANALYZE,
        headers=[("Origin", FOREIGN_ORIGIN), ("Origin", ALLOWED_ORIGIN)],
    )

    assert response.status_code == 403


# --- Where the gate sits in the stack -------------------------------------


def test_a_preflight_is_answered_without_reaching_the_gate(client):
    # CORSMiddleware is mounted outside the gate and answers OPTIONS itself,
    # which it has to: a preflight carries no body and is the request that
    # exists to ask whether the real one may be sent, so a gate that judged one
    # would refuse the question.
    response = client.options(
        ANALYZE,
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


@pytest.mark.parametrize("path", ["/healthz", "/readyz"])
def test_the_health_endpoints_ignore_the_origin(client, path):
    # The interface's availability poll runs in a browser and sends an origin;
    # the container healthcheck sends none. Neither is gated.
    response = client.get(path, headers={"Origin": FOREIGN_ORIGIN})

    assert response.status_code in (200, 503)


def test_the_root_is_not_gated(client):
    assert client.get("/", headers={"Origin": FOREIGN_ORIGIN}).status_code == 200


def test_a_mounted_application_is_still_gated():
    # Starlette strips `root_path` before matching, so a gate comparing the raw
    # path would not recognise a request served behind `--root-path` and would
    # call through silently. The gate reads the path through the shared helper
    # in `gate.py` for this reason.
    client_under_test = TestClient(
        stubbed(create_app(PRODUCTION)),
        root_path="/med-assist",
    )

    response = client_under_test.post(
        f"/med-assist{ANALYZE}", headers={"Origin": FOREIGN_ORIGIN}
    )

    assert response.status_code == 403


# --- Scopes that are not HTTP ---------------------------------------------


def socket_application() -> FastAPI:
    """An application with one WebSocket route behind the origin gate."""
    application = FastAPI()

    @application.websocket("/api/socket")
    async def socket(websocket: WebSocket) -> None:  # pylint: disable=W0612
        await websocket.accept()
        await websocket.send_text("through")

    application.add_middleware(
        RequireKnownOrigin, allowed_origins=DEFAULT_ALLOWED_ORIGINS
    )
    return application


def test_a_websocket_from_a_foreign_origin_is_refused_before_it_is_accepted():
    # No route here is a WebSocket today. The gate covers the scope anyway so
    # that the first `/api` socket anyone adds does not ship ungated - and a
    # socket is the one place where the browser's same-origin policy offers no
    # protection of its own at all.
    client_under_test = TestClient(socket_application())

    with pytest.raises(WebSocketDisconnect) as refused:
        with client_under_test.websocket_connect(
            "/api/socket", headers={"Origin": FOREIGN_ORIGIN}
        ):
            pass

    assert refused.value.code == 1008


def test_a_websocket_from_the_configured_origin_connects():
    client_under_test = TestClient(socket_application())

    with client_under_test.websocket_connect(
        "/api/socket", headers={"Origin": ALLOWED_ORIGIN}
    ) as connection:
        assert connection.receive_text() == "through"


# --- What is deliberately not gated ---------------------------------------


@pytest.mark.parametrize(
    "path", ["/healthz", "/readyz", "/", "/docs", "/redoc", "/openapi.json"]
)
def test_everything_outside_the_api_prefix_is_open(client, path):
    """
    The exact set of paths no gate covers, pinned so an addition is deliberate.

    The gate is a prefix, so a router mounted outside `/api` would ship ungated
    with nothing failing. This is the test that fails instead. The set is wider
    than "the health endpoints" and is meant to be: the schema endpoints are
    open too, and a deployment that does not want its API described to strangers
    keeps them off its proxy.
    """
    response = client.get(path, headers={"Origin": FOREIGN_ORIGIN})

    assert response.status_code != 403


# --- Gaps the review pass found -------------------------------------------


def test_an_oversized_foreign_body_is_refused_before_it_is_measured(client):
    """
    A refused document is never spooled to TMPDIR, and this is what proves it.

    The extractor-not-called assertions above would still hold if the whole body
    had been written to disk and then discarded. This one cannot: the size
    ceiling runs *inside* the origin gate, so a 413 here would mean the body had
    been read far enough to be measured. 403 means the request was refused on
    its headers with nothing read - the claim `origin.py` and the decision entry
    both make.
    """
    response = client.post(
        ANALYZE,
        content=b"x",
        headers={
            "Origin": FOREIGN_ORIGIN,
            "content-length": str(MAX_REQUEST_SIZE_BYTES + 1),
        },
    )

    assert response.status_code == 403
    assert response.json() == {"detail": {"message": FORBIDDEN}}


def test_an_allowed_origin_streams_as_before(client):
    # The refusal side of the streaming route is covered above; this is the
    # other half, so a gate that refused everything would not pass this file.
    response = client.post(STREAM, files=[txt()], headers={"Origin": ALLOWED_ORIGIN})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert [event for event in stream_events(response) if event["stage"] == "result"]


def test_the_header_name_is_read_case_insensitively():
    # `header()` lowercases the name it compares rather than trusting the ASGI
    # server to have normalised it. Built as a raw ASGI scope, because an HTTP
    # client normalises the name long before the server sees it.
    gate = RequireKnownOrigin(None, allowed_origins=DEFAULT_ALLOWED_ORIGINS)
    scope = {
        "type": "http",
        "path": ANALYZE,
        "headers": [(b"OrIgIn", FOREIGN_ORIGIN.encode())],
    }

    assert not gate.accepts(scope)


def test_a_padded_origin_value_still_matches():
    # `header()` strips the value. A proxy that pads the header must not turn an
    # allowed origin into a refusal.
    gate = RequireKnownOrigin(None, allowed_origins=DEFAULT_ALLOWED_ORIGINS)
    scope = {
        "type": "http",
        "path": ANALYZE,
        "headers": [(b"origin", f"  {ALLOWED_ORIGIN}  ".encode())],
    }

    assert gate.accepts(scope)


# --- What the allow-list does and does not keep private --------------------


@pytest.mark.parametrize(
    "origin,expected", [(ALLOWED_ORIGIN, 200), (FOREIGN_ORIGIN, 400)]
)
def test_the_preflight_reports_on_the_allow_list(origin, expected):
    """
    The allow-list is not a secret, asserted so the claim stays accurate.

    `CORSMiddleware` answers preflights itself, outside the gate, and its answer
    depends on the origin and on nothing else. Anyone who can reach the port can
    confirm a guess that way.

    This is pinned rather than fixed. Moving CORS inside the gate would refuse
    the preflight that exists to ask whether the real request may be sent, which
    breaks every browser. The documentation says the list is public instead.
    """
    client_under_test = TestClient(stubbed(create_app(PRODUCTION)))

    response = client_under_test.options(
        ANALYZE,
        headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
    )

    assert response.status_code == expected
