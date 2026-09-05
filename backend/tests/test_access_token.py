"""
The shared credential required in front of the analysis routes.

Four things are being pinned here, and only the first two are about who gets in:

- the gate refuses an anonymous caller on the analysis routes and nobody else,
- there is no configuration in which it is absent: a deployment that sets no
  credential does not start,
- it refuses on the request headers, before a byte of the body is read,
- and it never puts the credential anywhere - not in a message, not in a log.
"""

# pylint: disable=W0621

import json
import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request, WebSocket
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.access import (
    ACCESS_TOKEN_VARIABLE,
    MINIMUM_TOKEN_LENGTH,
    UNAUTHORIZED,
    AccessTokenError,
    RequireAccessToken,
    configured_access_token,
)
from app.core.dependencies import get_entity_extractor, get_text_extractor
from app.core.gate import covers
from app.core.middleware import REQUEST_TOO_LARGE, LimitRequestSize
from app.interfaces.service_interfaces import (
    EntityExtractionServiceInterface,
    TextExtractionServiceInterface,
)
from app.main import PRODUCTION, create_app
from app.schemas.extraction import EntityDetail
from tests.conftest import SUITE_TOKEN

# The suite's credential, generated in `conftest.py` and imported rather than
# written down again here. Two copies of a value long enough to be accepted by
# `configured_access_token` are two chances for one of them to be pasted into a
# `.env`, and AGENTS.md section 9 says no token is hardcoded in a test.
TOKEN = SUITE_TOKEN

ANALYZE = "/api/analyze"
STREAM = "/api/analyze/stream"

# The origin the default CORS configuration allows, so a refusal can be checked
# for the header a browser needs in order to read it at all.
ALLOWED_ORIGIN = "http://localhost:3000"


@pytest.fixture
def unset_token(monkeypatch):
    """
    No credential in the environment, whatever the machine running this has.

    `conftest.py` sets one for the whole suite, because `create_app` refuses to
    build without it. This undoes that for the few tests whose subject is the
    refusal itself.
    """
    monkeypatch.delenv(ACCESS_TOKEN_VARIABLE, raising=False)


@pytest.fixture
def set_token(monkeypatch):
    monkeypatch.setenv(ACCESS_TOKEN_VARIABLE, TOKEN)


def stubbed(app: FastAPI) -> FastAPI:
    """
    Put stub extractors in place of the ones that would read the weights.

    Needed even by the tests that never analyse anything: FastAPI solves a
    route's dependencies before it reports a malformed body, so a request that
    gets past the gate with no files still builds the real extractor - and that
    reads `NER_MODEL_NAME`, which no test environment sets.
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
def gated_client(set_token):
    return TestClient(stubbed(create_app(PRODUCTION)))


def bearer(token: str = TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def txt():
    return ("files", ("note.txt", b"contenu", "text/plain"))


def stream_events(response):
    """The `data:` payloads of a finished SSE response, decoded, in order."""
    return [
        json.loads(line.removeprefix("data:").strip())
        for line in response.text.splitlines()
        if line.startswith("data:")
    ]


# --- Reading the configuration -------------------------------------------


def test_no_variable_stops_the_process(unset_token):
    # There is no unconfigured mode. A deployment that sets nothing used to get
    # an open service that looked identical to a locked-down one from the
    # outside; now it gets a process that does not start.
    with pytest.raises(AccessTokenError):
        configured_access_token()


@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_a_blank_variable_stops_the_process(monkeypatch, blank):
    # A Compose passthrough with nothing behind it arrives as the empty string.
    # That is a deployment that did not configure a credential, and it is
    # refused exactly as an absent variable is - not accepted as the empty one.
    monkeypatch.setenv(ACCESS_TOKEN_VARIABLE, blank)

    with pytest.raises(AccessTokenError):
        configured_access_token()


def test_the_missing_credential_refusal_names_the_variable(unset_token):
    # The operator has to be able to act on it, and the variable name is the
    # only thing in this area that is safe to put in a message.
    with pytest.raises(AccessTokenError) as raised:
        configured_access_token()

    assert ACCESS_TOKEN_VARIABLE in str(raised.value)


def test_a_deployment_without_a_credential_does_not_start(unset_token):
    with pytest.raises(AccessTokenError):
        create_app(PRODUCTION)


def test_surrounding_whitespace_is_not_part_of_the_credential(monkeypatch):
    monkeypatch.setenv(ACCESS_TOKEN_VARIABLE, f"  {TOKEN}\n")

    assert configured_access_token() == TOKEN


def test_a_short_credential_stops_the_process(monkeypatch):
    monkeypatch.setenv(ACCESS_TOKEN_VARIABLE, "x" * (MINIMUM_TOKEN_LENGTH - 1))

    with pytest.raises(AccessTokenError):
        configured_access_token()


def test_the_refusal_does_not_quote_the_credential(monkeypatch):
    # The one value in this service's configuration that must never reach a log
    # line, and a startup refusal is exactly where a value normally would.
    short = "hunter2-hunter2"
    monkeypatch.setenv(ACCESS_TOKEN_VARIABLE, short)

    with pytest.raises(AccessTokenError) as raised:
        configured_access_token()

    assert short not in str(raised.value)
    assert ACCESS_TOKEN_VARIABLE in str(raised.value)


def test_the_minimum_length_itself_is_accepted(monkeypatch):
    exact = "y" * MINIMUM_TOKEN_LENGTH
    monkeypatch.setenv(ACCESS_TOKEN_VARIABLE, exact)

    assert configured_access_token() == exact


def test_a_configured_deployment_says_the_browser_cannot_use_it(set_token, caplog):
    # Entered as a context manager so the lifespan runs, which is where the
    # posture line is written. `caplog` attaches its own handler, so this sees
    # the record whether or not a real deployment's logging configuration would
    # - see the lifespan's docstring for that limit. What is pinned here is the
    # content: it names the proxy, and it does not name the credential.
    with caplog.at_level(logging.INFO, logger="app.main"):
        with TestClient(stubbed(create_app(PRODUCTION))):
            pass

    assert TOKEN not in caplog.text
    assert "proxy" in caplog.text


# --- What the gate covers ------------------------------------------------


@pytest.mark.parametrize("path", [ANALYZE, STREAM])
def test_both_analysis_routes_refuse_an_anonymous_caller(gated_client, path):
    response = gated_client.post(path)

    assert response.status_code == 401
    assert response.json() == {"detail": {"message": UNAUTHORIZED}}
    assert response.headers["WWW-Authenticate"] == "Bearer"


@pytest.mark.parametrize("path", ["/healthz", "/readyz", "/"])
def test_the_open_paths_stay_open(gated_client, path):
    # The container healthcheck calls readiness from inside the container and
    # the frontend's availability poll calls it from a browser that cannot hold
    # a secret. Gating either would break one of them and disclose nothing.
    assert gated_client.get(path).status_code == 200


def test_a_valid_credential_reaches_the_route(gated_client):
    # Past the gate, so the missing body is what fails - the same 422 the
    # ungated deployment answers.
    assert gated_client.post(ANALYZE, headers=bearer()).status_code == 422


def test_a_wrong_credential_is_refused_exactly_as_a_missing_one(gated_client):
    absent = gated_client.post(ANALYZE)
    wrong = gated_client.post(ANALYZE, headers=bearer("z" * len(TOKEN)))

    # Byte for byte: which of the two it was is not the caller's to learn.
    assert wrong.status_code == absent.status_code
    assert wrong.json() == absent.json()


@pytest.mark.parametrize(
    "header",
    [
        TOKEN,  # no scheme at all
        f"Basic {TOKEN}",
        f"Token {TOKEN}",
        "Bearer",  # scheme with no credential
        f"Bearer {TOKEN} extra",
        f"Bearer {TOKEN[:-1]}",
        f"Bearer {TOKEN}x",
        "Bearer ",
    ],
)
def test_a_credential_that_is_not_the_configured_one_is_refused(gated_client, header):
    response = gated_client.post(ANALYZE, headers={"Authorization": header})

    assert response.status_code == 401


@pytest.mark.parametrize("scheme", ["Bearer", "bearer", "BEARER", "BeArEr"])
def test_the_scheme_is_read_case_insensitively(gated_client, scheme):
    # RFC 9110 makes the scheme case-insensitive, and a client library that
    # spells it lowercase is not a caller to refuse.
    response = gated_client.post(
        ANALYZE, headers={"Authorization": f"{scheme} {TOKEN}"}
    )

    assert response.status_code == 422


@pytest.mark.parametrize("method", ["get", "head", "put", "delete", "patch"])
def test_the_gate_does_not_care_which_method_is_used(gated_client, method):
    # `covers` only ever looks at the path. A method the route does not even
    # support must still be refused for lack of a credential rather than
    # answered 404/405 - the latter would let an anonymous caller learn
    # something about the route before proving who it is.
    response = getattr(gated_client, method)(ANALYZE)

    assert response.status_code == 401


def test_a_non_preflight_options_request_is_still_gated(gated_client):
    # CORSMiddleware only answers an OPTIONS itself when it carries
    # Access-Control-Request-Method - the marker of an actual preflight. A bare
    # OPTIONS, the kind a non-browser client might send, is an ordinary request
    # to the gate and must not be waved through just because of its method.
    response = gated_client.options(ANALYZE)

    assert response.status_code == 401


# --- What the refusal carries --------------------------------------------


def test_the_refusal_is_readable_by_a_browser(gated_client):
    response = gated_client.post(ANALYZE, headers={"Origin": ALLOWED_ORIGIN})

    # CORS is mounted outside the gate, so the 401 carries the allow-origin
    # header. Without it the browser reports an opaque network error and the
    # interface cannot tell a refusal from an unreachable backend.
    assert response.status_code == 401
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_the_refusal_is_not_cached(gated_client):
    response = gated_client.post(ANALYZE)

    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("path", [ANALYZE, STREAM])
def test_a_preflight_is_answered_without_a_credential(gated_client, path):
    # A browser sends no Authorization on a preflight. A gate that saw one
    # would refuse the request whose entire purpose is to ask whether the real
    # one may carry the header. Both analysis routes go through the same
    # CORSMiddleware, so both are checked rather than assuming they agree.
    response = gated_client.options(
        path,
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_the_stream_refusal_is_json_before_any_stream_opens(gated_client):
    # The refusal is written by the same `unauthorized()` JSONResponse the
    # plain endpoint sends, from middleware that runs before FastAPI ever
    # builds the route's async generator. Nothing SSE-shaped should reach the
    # caller: no event-stream content type, no `data:` framing.
    response = gated_client.post(STREAM)

    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/json")
    assert not response.headers["content-type"].startswith("text/event-stream")
    assert response.json() == {"detail": {"message": UNAUTHORIZED}}
    assert stream_events(response) == []


def test_the_credential_never_reaches_a_log_line(gated_client, caplog):
    with caplog.at_level(logging.DEBUG):
        gated_client.post(ANALYZE, headers=bearer(f"{TOKEN[:-4]}wrong"))

    # Not truncated, not prefixed, not "the first eight characters". A near miss
    # in a log file is a working credential for whoever reads the log.
    assert TOKEN[:-4] not in caplog.text
    assert "wrong" not in caplog.text


# --- A second header cannot smuggle a credential past the first ----------


def test_a_valid_first_header_is_used_even_with_a_bad_one_after_it(gated_client):
    # `presented_credential` reads only the first `Authorization` header, which
    # is also what a proxy in front of this process will have read. This is the
    # accepting side of that choice.
    response = gated_client.post(
        ANALYZE,
        headers=[("Authorization", f"Bearer {TOKEN}"), ("Authorization", "Bearer z")],
    )

    assert response.status_code == 422  # past the gate, missing body


def test_an_invalid_first_header_is_not_rescued_by_a_valid_one_after_it(gated_client):
    # The other side of the same choice: a caller (or an intermediary) cannot
    # get in by appending a correct guess after a wrong first attempt.
    response = gated_client.post(
        ANALYZE,
        headers=[("Authorization", "Bearer z"), ("Authorization", f"Bearer {TOKEN}")],
    )

    assert response.status_code == 401


# --- The gate runs before the body is read -------------------------------


@pytest.fixture
def ordered_client():
    """
    The two body-facing middlewares in the order `create_app` mounts them.

    The ceiling is tiny so an oversized body is a few kilobytes rather than
    fifty megabytes; what is being pinned is which of the two answers first.
    """
    app = FastAPI()

    @app.post("/api/echo")
    async def echo(request: Request):  # pylint: disable=W0612
        return {"received_bytes": len((await request.body()))}

    app.add_middleware(LimitRequestSize, max_bytes=1024)
    app.add_middleware(RequireAccessToken, token=TOKEN)
    return TestClient(app)


def test_an_anonymous_oversized_body_is_refused_before_it_is_measured(ordered_client):
    response = ordered_client.post("/api/echo", content=b"x" * 4096)

    # 401 rather than 413 is the whole point: the refusal was decided from the
    # headers, so the body was never read and never spooled to TMPDIR. A route
    # dependency could not do this - FastAPI parses a multipart body before it
    # solves one.
    assert response.status_code == 401


def test_an_authenticated_oversized_body_still_meets_the_ceiling(ordered_client):
    response = ordered_client.post("/api/echo", content=b"x" * 4096, headers=bearer())

    assert response.status_code == 413
    assert response.json()["detail"]["message"] == REQUEST_TOO_LARGE


def test_a_path_outside_the_prefix_is_not_gated(ordered_client):
    @ordered_client.app.get("/elsewhere")
    async def elsewhere():  # pylint: disable=W0612
        return {"ok": True}

    assert ordered_client.get("/elsewhere").status_code == 200


def test_the_real_app_mounts_the_gate_outside_the_size_ceiling(gated_client):
    # `ordered_client` above pins the *behaviour* on a minimal app built for the
    # purpose. This pins the same fact on the application `create_app` actually
    # builds, so a future reordering of `add_middleware` calls in `app.main`
    # fails a test here rather than only being noticed as a change in which
    # status code an oversized anonymous request gets.
    classes = [middleware.cls for middleware in gated_client.app.user_middleware]

    assert classes.index(RequireAccessToken) < classes.index(LimitRequestSize)


# --- End to end, with the model stubbed out ------------------------------


def test_an_authenticated_batch_is_analysed_as_before(gated_client):
    response = gated_client.post(ANALYZE, files=[txt()], headers=bearer())

    assert response.status_code == 200
    assert "summary" in response.json()


def test_an_anonymous_batch_is_refused_without_being_analysed(gated_client):
    response = gated_client.post(ANALYZE, files=[txt()])

    assert response.status_code == 401
    entity_extractor = gated_client.app.dependency_overrides[get_entity_extractor]()
    entity_extractor.extract_entities.assert_not_called()


def test_an_authenticated_stream_is_analysed_as_before(gated_client):
    response = gated_client.post(STREAM, files=[txt()], headers=bearer())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    [result] = [
        event for event in stream_events(response) if event["stage"] == "result"
    ]
    assert "summary" in result["result"]


def test_an_anonymous_stream_batch_is_refused_without_being_analysed(gated_client):
    response = gated_client.post(STREAM, files=[txt()])

    assert response.status_code == 401
    entity_extractor = gated_client.app.dependency_overrides[get_entity_extractor]()
    entity_extractor.extract_entities.assert_not_called()


# --- The gate matches the path the router matches ------------------------


def test_a_mounted_application_is_still_gated(set_token):
    """
    The bypass this test exists for: an app served behind a prefix.

    Starlette's router strips `root_path` before matching, so under
    `--root-path /med-assist` a request for `/med-assist/api/analyze` reaches
    the route registered as `/api/analyze`. A gate comparing the raw path would
    not recognise it, would call through silently, and the batch would be
    analysed - the control absent on precisely the deployment that added a
    proxy, which is the deployment this feature exists for.
    """
    client = TestClient(stubbed(create_app(PRODUCTION)), root_path="/med-assist")

    assert client.post(f"/med-assist{ANALYZE}").status_code == 401


def test_a_mounted_application_still_accepts_the_credential(set_token):
    client = TestClient(stubbed(create_app(PRODUCTION)), root_path="/med-assist")

    response = client.post(f"/med-assist{ANALYZE}", headers=bearer())

    assert response.status_code == 422


def test_a_mounted_health_endpoint_stays_open(set_token):
    client = TestClient(stubbed(create_app(PRODUCTION)), root_path="/med-assist")

    assert client.get("/med-assist/readyz").status_code == 200


# --- Scopes that are not HTTP --------------------------------------------


def socket_application() -> FastAPI:
    """An application with one WebSocket route behind the gate."""
    application = FastAPI()

    @application.websocket("/api/socket")
    async def socket(websocket: WebSocket) -> None:  # pylint: disable=W0612
        await websocket.accept()
        await websocket.send_text("through")

    application.add_middleware(RequireAccessToken, token=TOKEN)
    return application


def test_a_websocket_on_the_prefix_is_refused_before_it_is_accepted():
    # No route here is a WebSocket today. The gate covers the scope anyway so
    # that the first `/api` socket anyone adds does not ship ungated with
    # nothing failing, and this test is what would notice if the exemption came
    # back.
    client = TestClient(socket_application())

    with pytest.raises(WebSocketDisconnect) as refused:
        with client.websocket_connect("/api/socket"):
            pass

    assert refused.value.code == 1008


def test_a_websocket_carrying_the_credential_connects():
    client = TestClient(socket_application())

    with client.websocket_connect("/api/socket", headers=bearer()) as connection:
        assert connection.receive_text() == "through"


# --- Which routes the gate does and does not cover ------------------------


# Every path the application serves outside the `/api` prefix, and therefore
# every path a configured deployment still answers anonymously. Pinned as a
# literal set so that a router mounted outside `/api` fails this test rather
# than shipping ungated in silence - the enumeration in `RequireAccessToken`'s
# docstring, in deploy/README.md and in the decision entry has to stay true.
UNGATED_PATHS = {
    "/",
    "/healthz",
    "/readyz",
    "/docs",
    "/docs/oauth2-redirect",
    "/redoc",
    "/openapi.json",
}


def test_the_ungated_paths_are_exactly_the_documented_set(set_token):
    # `covers` is shared by both gates, so this pins the reach of the origin
    # gate at the same time as the credential one.
    application = create_app(PRODUCTION)

    ungated = {route.path for route in application.routes if not covers(route.path)}

    assert ungated == UNGATED_PATHS


def test_every_analysis_route_is_gated(set_token):
    application = create_app(PRODUCTION)

    analysis = [route.path for route in application.routes if "analyze" in route.path]

    assert analysis
    assert all(covers(path) for path in analysis)


def test_the_schema_endpoints_answer_a_gated_deployment_anonymously(gated_client):
    # Not a hole to fix here - it is the documented consequence of gating a
    # prefix - but it is asserted so that the documentation saying so cannot
    # quietly stop being true. The proxy example routes only /api and the two
    # health paths, so these are unreachable there.
    assert gated_client.get("/openapi.json").status_code == 200


def test_a_short_credential_stops_the_application_not_just_the_helper(monkeypatch):
    monkeypatch.setenv(ACCESS_TOKEN_VARIABLE, "too-short")

    with pytest.raises(AccessTokenError):
        create_app(PRODUCTION)
