"""
Test-wide fixtures.

Both things here exist because the application refuses to start on a
configuration it will not serve safely, so the suite has to supply one - and
because the settings classes read a `.env` file as well as the environment, so a
developer's own would otherwise decide what the suite tests.
"""

import os
import secrets

import pytest
from pydantic_settings import BaseSettings

from app.core.access import ACCESS_TOKEN_VARIABLE, AccessTokenConfiguration
from app.core.config import CORSConfiguration, NERModelConfiguration
from app.core.origin import ORIGIN_VARIABLE

# Every settings class in the application. Listed rather than discovered so
# that adding one is a deliberate line here: pydantic merges `model_config`
# into each subclass at class creation, so patching `BaseSettings` itself
# reaches none of them.
SETTINGS_CLASSES: tuple[type[BaseSettings], ...] = (
    AccessTokenConfiguration,
    CORSConfiguration,
    NERModelConfiguration,
)

# The credential the suite runs under unless a test says otherwise. It has to be
# here rather than in each test module because `create_app` now refuses to build
# an application without one: every test that builds the app needs a credential,
# including the several hundred that have nothing to do with this feature.
#
# Generated rather than written down. A literal long enough to satisfy
# `MINIMUM_TOKEN_LENGTH` is a literal a deployment would accept verbatim if
# anyone ever pasted it into a `.env`, and AGENTS.md section 9 says no token is
# hardcoded in code, tests or docs. Generating it also means the suite cannot
# quietly come to depend on a particular value.
#
# It lives here and only here. `test_access_token.py` imports it rather than
# declaring its own, so the two cannot drift.
SUITE_TOKEN = secrets.token_urlsafe(32)

# Set at import rather than only in the fixture below, and this is load-bearing.
# `app/main.py` builds an application at module scope for `uvicorn app.main:app`
# to import, so `create_app` runs the moment a test module imports `app.main` -
# during collection, before any fixture for any test has been set up. A fixture
# alone leaves every module that imports it failing to collect at all.
#
# Assigned rather than defaulted. `setdefault` looked considerate - it would
# keep a value a developer had exported - but the autouse fixture below
# overwrites the variable for every test anyway, so the only thing it preserved
# was the value used during collection. That is the one place it could do harm:
# an exported credential under the minimum length made `app.main` raise while
# being imported, so the whole suite failed to collect, pointing at an
# environment variable rather than at a test.
os.environ[ACCESS_TOKEN_VARIABLE] = SUITE_TOKEN

# The origin allow-list is now enforced, so an exported `CORS_ALLOWED_ORIGINS`
# would change what the origin gate accepts and make `test_origin_gate.py` fail
# against a value it never mentions - or, if the exported value is malformed,
# make every `create_app()` in the suite raise `CORSOriginError`. The suite
# tests the default; a test that wants another list sets it itself.
os.environ.pop(ORIGIN_VARIABLE, None)


def bearer_headers(token: str = SUITE_TOKEN) -> dict[str, str]:
    """
    The credential header, for a test that drives the whole application.

    A test that builds its app with `create_app` goes through the credential
    gate like any other caller, so one that is about something else - the size
    ceiling, the readiness refusal, a route that no longer exists - has to
    present a credential to reach the behaviour it is actually pinning. Passing
    these to `TestClient(app, headers=...)` sets them on every request that
    client makes.

    Tests about the gate itself do not use this. They build their headers by
    hand, because the value under test is the header.

    :param token: The credential to present. Defaults to the suite's.
    :return: An `Authorization` header presenting `token` as a bearer.
    """
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def ignore_the_developers_env_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Read settings from the environment only, never from `backend/.env`.

    The settings classes declare `env_file=".env"`, which pydantic-settings
    reads relative to the working directory - `backend/`, when the suite is run
    the documented way. That file is gitignored and personal, so without this
    the suite's results depend on what a particular machine happens to have in
    it.

    The credential is the sharp case. A developer whose `.env` sets
    `API_ACCESS_TOKEN` turns every "no credential is configured" fixture into a
    gated application, and one whose value is under the minimum length makes
    every `create_app()` in the whole suite raise `AccessTokenError` - a failure
    in tests that have nothing to do with this feature, pointing at a file that
    is not in the repository.

    The variable is then set to a known value rather than cleared. Clearing it
    was right while the gate was optional and the unconfigured application was
    the one most tests wanted; now that `create_app` refuses to build without a
    credential, clearing it would fail every test in the suite that builds an
    app. A test that wants the refusal deletes the variable itself, and one that
    wants a different value overwrites it - either way it says so in its own
    body rather than inheriting it from the machine.
    """
    for settings_class in SETTINGS_CLASSES:
        monkeypatch.setitem(settings_class.model_config, "env_file", None)
    monkeypatch.setenv(ACCESS_TOKEN_VARIABLE, SUITE_TOKEN)
    monkeypatch.delenv(ORIGIN_VARIABLE, raising=False)
