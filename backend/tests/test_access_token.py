"""
The optional shared credential in front of the analysis routes.

Three things are being pinned here, and only the first is about who gets in:

- the gate refuses an anonymous caller on the analysis routes and nobody else,
- it refuses on the request headers, before a byte of the body is read,
- and it never puts the credential anywhere - not in a message, not in a log.
"""

# pylint: disable=W0621

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.core.access import (
    ACCESS_TOKEN_VARIABLE,
    MINIMUM_TOKEN_LENGTH,
    UNAUTHORIZED,
    AccessTokenError,
    RequireAccessToken,
    configured_access_token,
)
from app.core.dependencies import get_entity_extractor, get_text_extractor
from app.core.middleware import REQUEST_TOO_LARGE, LimitRequestSize
from app.interfaces.service_interfaces import (
    EntityExtractionServiceInterface,
    TextExtractionServiceInterface,
)
from app.main import PRODUCTION, create_app
from app.schemas.extraction import EntityDetail

# A credential of the shape an operator would generate, long enough to pass the
# minimum. It is a test fixture and not a secret anywhere: nothing outside this
# file reads it, and no deployment config in this repository names a value.
TOKEN = "test-credential-0123456789abcdefghijklmn"

ANALYZE = "/api/analyze"
STREAM = "/api/analyze/stream"

# The origin the default CORS configuration allows, so a refusal can be checked
# for the header a browser needs in order to read it at all.
ALLOWED_ORIGIN = "http://localhost:3000"


@pytest.fixture
def unset_token(monkeypatch):
    """No credential in the environment, whatever the machine running this has."""
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
def open_client(unset_token):
    """The application as an unconfigured deployment runs it: no gate."""
    return TestClient(stubbed(create_app(PRODUCTION)))


@pytest.fixture
def gated_client(set_token):
    return TestClient(stubbed(create_app(PRODUCTION)))


def bearer(token: str = TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def txt():
    return ("files", ("note.txt", b"contenu", "text/plain"))


# --- Reading the configuration -------------------------------------------


def test_no_variable_configures_no_credential(unset_token):
    assert configured_access_token() == ""


@pytest.mark.parametrize("blank", ["", "   ", "\t\n"])
def test_a_blank_variable_reads_as_unconfigured(monkeypatch, blank):
    # A Compose passthrough with nothing behind it arrives as the empty string,
    # and that is a deployment that did not configure a credential rather than
    # one that configured the empty one.
    monkeypatch.setenv(ACCESS_TOKEN_VARIABLE, blank)

    assert configured_access_token() == ""


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


def test_a_deployment_without_a_credential_is_told_so(unset_token, caplog):
    with caplog.at_level(logging.WARNING, logger="app.main"):
        create_app(PRODUCTION)

    # The mitigation for the one way this feature fails open: a mistyped
    # variable name leaves the routes answering anyone, and looks identical to
    # a deployment that locked them down.
    assert ACCESS_TOKEN_VARIABLE in caplog.text


def test_a_configured_deployment_says_the_browser_cannot_use_it(set_token, caplog):
    with caplog.at_level(logging.INFO, logger="app.main"):
        create_app(PRODUCTION)

    assert TOKEN not in caplog.text
    assert "proxy" in caplog.text


# --- What the gate covers ------------------------------------------------


def test_without_a_credential_configured_nothing_is_refused(open_client):
    # 422 rather than 401: the body is missing, which is the answer this request
    # got before the gate existed and has to keep getting.
    assert open_client.post(ANALYZE).status_code == 422


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


def test_a_preflight_is_answered_without_a_credential(gated_client):
    # A browser sends no Authorization on a preflight. A gate that saw one
    # would refuse the request whose entire purpose is to ask whether the real
    # one may carry the header.
    response = gated_client.options(
        ANALYZE,
        headers={
            "Origin": ALLOWED_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ALLOWED_ORIGIN


def test_the_credential_never_reaches_a_log_line(gated_client, caplog):
    with caplog.at_level(logging.DEBUG):
        gated_client.post(ANALYZE, headers=bearer(f"{TOKEN[:-4]}wrong"))

    # Not truncated, not prefixed, not "the first eight characters". A near miss
    # in a log file is a working credential for whoever reads the log.
    assert TOKEN[:-4] not in caplog.text
    assert "wrong" not in caplog.text


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


# --- End to end, with the model stubbed out ------------------------------


def test_an_authenticated_batch_is_analysed_as_before(gated_client):
    response = gated_client.post(ANALYZE, files=[txt()], headers=bearer())

    assert response.status_code == 200
    assert "summary" in response.json()


def test_an_anonymous_batch_is_refused_without_being_analysed(gated_client):
    response = gated_client.post(ANALYZE, files=[txt()])

    assert response.status_code == 401


def test_an_unconfigured_deployment_still_analyses_anonymously(open_client):
    # The contract as it stands today. A deployment that sets nothing must see
    # no change at all from this feature existing.
    response = open_client.post(ANALYZE, files=[txt()])

    assert response.status_code == 200
    assert "summary" in response.json()
