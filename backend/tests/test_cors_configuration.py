"""Which origins the application ends up allowing, and why never a wildcard.

Everything here asserts against the middleware `create_app` actually built, not
against the parser alone: a variable can be read perfectly and dropped on the
way to `add_middleware`, and every parsing test would still pass.
"""

# pylint: disable=W0621
import pytest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.testclient import TestClient

from app import main
from app.core.config import (
    DEFAULT_ALLOWED_ORIGINS,
    WILDCARD,
    CORSConfiguration,
    CORSOriginError,
)
from app.core.middleware import MAX_REQUEST_SIZE_BYTES
from app.main import PRODUCTION, create_app
from tests.conftest import bearer_headers

VARIABLE = "CORS_ALLOWED_ORIGINS"

LOCAL_FRONTEND = "http://localhost:3000"


@pytest.fixture(autouse=True)
def a_clean_environment(monkeypatch, tmp_path):
    """
    Nothing inherited, so each case sets its own value.

    The settings class reads a `.env` beside the working directory, which
    `delenv` cannot reach: run from an empty directory, or the default-value
    cases assert what ships while a developer's local `.env` supplies
    something else.
    """
    monkeypatch.delenv(VARIABLE, raising=False)
    monkeypatch.chdir(tmp_path)


def allowed_origins(app):
    """Read the origin list out of the CORS middleware the app was built with."""
    for middleware in app.user_middleware:
        if middleware.cls is CORSMiddleware:
            return middleware.kwargs["allow_origins"]
    raise AssertionError("The application was built without CORS middleware")


def built_with(monkeypatch, value=None):
    if value is not None:
        monkeypatch.setenv(VARIABLE, value)
    return allowed_origins(create_app(PRODUCTION))


def test_an_unset_variable_keeps_the_local_frontend(monkeypatch):
    assert built_with(monkeypatch) == [LOCAL_FRONTEND]


def test_the_shipped_default_is_the_local_frontend():
    assert DEFAULT_ALLOWED_ORIGINS == (LOCAL_FRONTEND,)


def test_one_configured_origin_replaces_the_default(monkeypatch):
    assert built_with(monkeypatch, "https://med-assist.example.org") == [
        "https://med-assist.example.org"
    ]


def test_several_origins_are_comma_separated(monkeypatch):
    value = "https://a.example.org,https://b.example.org:8443,http://localhost:3000"

    assert built_with(monkeypatch, value) == [
        "https://a.example.org",
        "https://b.example.org:8443",
        LOCAL_FRONTEND,
    ]


def test_whitespace_around_an_entry_is_trimmed(monkeypatch):
    value = "  https://a.example.org ,\n\thttps://b.example.org  "

    assert built_with(monkeypatch, value) == [
        "https://a.example.org",
        "https://b.example.org",
    ]


def test_an_empty_entry_is_dropped_rather_than_allowed(monkeypatch):
    assert built_with(monkeypatch, "https://a.example.org,,") == [
        "https://a.example.org"
    ]


def test_a_trailing_slash_is_dropped_instead_of_never_matching(monkeypatch):
    # Starlette compares the Origin header against these strings literally, so
    # the slashed form allows nothing at all and says nothing about it.
    assert built_with(monkeypatch, "http://localhost:3000/") == [LOCAL_FRONTEND]


def test_the_host_is_lowercased(monkeypatch):
    # A browser sends the origin lowercased; a literal comparison against a
    # capitalised host would never match.
    assert built_with(monkeypatch, "HTTPS://A.Example.ORG") == ["https://a.example.org"]


@pytest.mark.parametrize("value", ["", "   ", ",", " , "])
def test_a_value_holding_nothing_falls_back_rather_than_opening_up(monkeypatch, value):
    assert built_with(monkeypatch, value) == [LOCAL_FRONTEND]


def test_a_wildcard_is_refused_at_startup(monkeypatch):
    monkeypatch.setenv(VARIABLE, WILDCARD)

    with pytest.raises(CORSOriginError) as refusal:
        create_app(PRODUCTION)

    assert WILDCARD in str(refusal.value)
    assert "credential" in str(refusal.value)


def test_a_wildcard_among_real_origins_is_refused_too(monkeypatch):
    monkeypatch.setenv(VARIABLE, "https://a.example.org,*")

    with pytest.raises(CORSOriginError):
        create_app(PRODUCTION)


def test_the_wildcard_never_reaches_credentialed_middleware(monkeypatch):
    # `allow_credentials=True` with `*` is a spec violation and, where a server
    # echoes the origin back, a real hole. Asserted against a configured value
    # rather than the default, so the pairing is checked on the path an
    # operator's own list actually takes.
    monkeypatch.setenv(VARIABLE, "https://a.example.org")
    app = create_app(PRODUCTION)
    cors = next(m for m in app.user_middleware if m.cls is CORSMiddleware)

    assert cors.kwargs["allow_credentials"] is True
    assert cors.kwargs["allow_origins"] == ["https://a.example.org"]
    assert WILDCARD not in cors.kwargs["allow_origins"]


@pytest.mark.parametrize(
    "value",
    [
        "http://localhost:3000/app",  # a path
        "http://localhost:3000?a=1",  # a query
        "http://localhost:3000#top",  # a fragment
        "localhost:3000",  # no scheme
        "ftp://localhost",  # not a browser origin
        "file://",  # no host
        "http://user:pass@localhost:3000",  # credentials
        "http://localhost:port",  # a port that is not a number
        "http://localhost:99999",  # a port out of range
        "http://localhost:0",  # a port nothing can listen on
        "http://localhost:",  # a dangling colon, which parses as no port
        "http://[::1:3000",  # an unbalanced IPv6 bracket
        "https://*.example.org",  # a pattern; the middleware matches literally
        "https://hôpital.example.org",  # not the punycode a browser sends
        "http://a b:3000",  # a space in the host
        '["http://localhost:3000"]',  # the JSON spelling this does not accept
    ],
)
def test_a_value_that_is_not_an_origin_is_refused(monkeypatch, value):
    monkeypatch.setenv(VARIABLE, value)

    with pytest.raises(CORSOriginError):
        create_app(PRODUCTION)


def test_the_refusal_points_at_the_entry_without_quoting_it(monkeypatch):
    hostname = "internal-hospital-host.invalid"
    monkeypatch.setenv(VARIABLE, f"https://a.example.org,https://{hostname}/wards")

    with pytest.raises(CORSOriginError) as refusal:
        create_app(PRODUCTION)

    # An origin is deployment configuration and can name an internal host, so
    # the message says which entry is wrong rather than what it said.
    assert "entry 2" in str(refusal.value)
    assert hostname not in str(refusal.value)


@pytest.mark.parametrize(
    "entry",
    [
        # Both of these raise inside `urlsplit` itself rather than in the
        # checks after it, and the standard library quotes what it choked on.
        # Escaping as a ValueError would have pydantic wrap it in a
        # ValidationError that echoes the whole variable back into the log.
        "https://[{hostname}:8443",
        "https://{hostname}℀",
    ],
)
def test_a_value_the_parser_itself_rejects_leaks_nothing_either(monkeypatch, entry):
    hostname = "internal-hospital-host.invalid"
    monkeypatch.setenv(VARIABLE, entry.format(hostname=hostname))

    with pytest.raises(CORSOriginError) as refusal:
        create_app(PRODUCTION)

    assert "entry 1" in str(refusal.value)
    assert hostname not in str(refusal.value)


@pytest.mark.parametrize(
    "value, expected",
    [
        # A browser leaves an implicit port out of the Origin header, so an
        # entry that spells it out matches nothing at all.
        ("https://a.example.org:443", "https://a.example.org"),
        ("http://a.example.org:80", "http://a.example.org"),
        # ... and keeps one that is not implicit.
        ("https://a.example.org:8443", "https://a.example.org:8443"),
        ("http://a.example.org:443", "http://a.example.org:443"),
        # An IPv6 literal keeps its brackets, which is how a browser sends it.
        ("http://[::1]:3000", "http://[::1]:3000"),
        ("http://[::1]:80", "http://[::1]"),
    ],
)
def test_an_origin_is_rewritten_the_way_a_browser_sends_it(
    monkeypatch, value, expected
):
    assert built_with(monkeypatch, value) == [expected]


def test_the_field_name_works_as_well_as_the_alias():
    # Without `populate_by_name`, the field name is dropped as an extra and the
    # caller silently gets the default instead of what they asked for.
    config = CORSConfiguration(
        allowed_origins=["https://a.example.org"], _env_file=None
    )

    assert config.allowed_origins == ("https://a.example.org",)


def test_a_list_passed_directly_is_normalised_the_same_way():
    # The settings object is constructible in code as well as from the
    # environment, and the same rules have to hold on that path.
    config = CORSConfiguration(
        CORS_ALLOWED_ORIGINS=[" http://localhost:3000/ "], _env_file=None
    )

    assert config.allowed_origins == (LOCAL_FRONTEND,)


@pytest.fixture
def stubbed_model(monkeypatch):
    """Building the app loads the weights at startup; nothing here needs them."""
    monkeypatch.setattr(main, "get_entity_extractor", lambda: object())


def test_a_configured_origin_is_allowed_on_a_real_response(monkeypatch, stubbed_model):
    monkeypatch.setenv(VARIABLE, "https://med-assist.example.org")

    with TestClient(create_app(PRODUCTION)) as client:
        response = client.get("/", headers={"Origin": "https://med-assist.example.org"})

    assert response.headers["access-control-allow-origin"] == (
        "https://med-assist.example.org"
    )
    assert response.headers["access-control-allow-credentials"] == "true"


def test_an_origin_outside_the_list_gets_no_allow_header(monkeypatch, stubbed_model):
    monkeypatch.setenv(VARIABLE, "https://med-assist.example.org")

    with TestClient(create_app(PRODUCTION)) as client:
        response = client.get("/", headers={"Origin": "https://elsewhere.example.org"})

    assert "access-control-allow-origin" not in response.headers


def test_the_default_still_answers_the_local_frontend(monkeypatch, stubbed_model):
    with TestClient(create_app(PRODUCTION)) as client:
        preflight = client.options(
            "/api/analyze",
            headers={
                "Origin": LOCAL_FRONTEND,
                "Access-Control-Request-Method": "POST",
            },
        )

    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == LOCAL_FRONTEND


def test_a_preflight_from_a_disallowed_origin_is_refused(monkeypatch, stubbed_model):
    # A GET from a disallowed origin merely lacks the allow header (the
    # browser is what enforces the block); a preflight is where Starlette's
    # CORSMiddleware actively refuses, so the negative case is asserted here
    # too rather than assumed from the GET case above.
    monkeypatch.setenv(VARIABLE, "https://med-assist.example.org")

    with TestClient(create_app(PRODUCTION)) as client:
        preflight = client.options(
            "/api/analyze",
            headers={
                "Origin": "https://elsewhere.example.org",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert preflight.status_code == 400
    assert "access-control-allow-origin" not in preflight.headers


def test_a_refused_oversized_request_still_carries_the_allow_header(
    monkeypatch, stubbed_model
):
    # CORSMiddleware is registered outside the size ceiling on purpose:
    # LimitRequestSize writes its 413 straight to `send`, so without CORS
    # outside it the browser sees an opaque network error rather than a refusal
    # and the frontend's `too_large` branch is unreachable. Reading the origins
    # from the environment must not disturb that ordering.
    origin = "https://med-assist.example.org"
    monkeypatch.setenv(VARIABLE, origin)

    with TestClient(create_app(PRODUCTION), headers=bearer_headers()) as client:
        response = client.post(
            "/api/analyze",
            content=b"x",
            headers={
                "Origin": origin,
                "content-length": str(MAX_REQUEST_SIZE_BYTES + 1),
            },
        )

    assert response.status_code == 413
    assert response.headers["access-control-allow-origin"] == origin
