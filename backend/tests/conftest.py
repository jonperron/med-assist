"""
Test-wide fixtures.

The one thing here exists because the settings classes read a `.env` file as
well as the environment, so a developer's own would otherwise decide what the
suite tests.
"""

import os

import pytest
from pydantic_settings import BaseSettings

from app.core.config import CORSConfiguration, NERModelConfiguration
from app.core.origin import ORIGIN_VARIABLE

# Every settings class in the application. Listed rather than discovered so
# that adding one is a deliberate line here: pydantic merges `model_config`
# into each subclass at class creation, so patching `BaseSettings` itself
# reaches none of them.
SETTINGS_CLASSES: tuple[type[BaseSettings], ...] = (
    CORSConfiguration,
    NERModelConfiguration,
)

# Cleared at import rather than only in the fixture below, and this is
# load-bearing. `app/main.py` builds an application at module scope for
# `uvicorn app.main:app` to import, so `create_app` runs the moment a test
# module imports `app.main` - during collection, before any fixture for any test
# has been set up. A fixture alone leaves every module that imports it failing
# to collect at all.
#
# The origin allow-list is enforced, so an exported `CORS_ALLOWED_ORIGINS` would
# change what the origin gate accepts and make `test_origin_gate.py` fail
# against a value it never mentions - or, if the exported value is malformed,
# make every `create_app()` in the suite raise `CORSOriginError`. The suite tests
# the default; a test that wants another list sets it itself.
os.environ.pop(ORIGIN_VARIABLE, None)


@pytest.fixture(autouse=True)
def ignore_the_developers_env_file(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Read settings from the environment only, never from `backend/.env`.

    The settings classes declare `env_file=".env"`, which pydantic-settings
    reads relative to the working directory - `backend/`, when the suite is run
    the documented way. That file is gitignored and personal, so without this
    the suite's results depend on what a particular machine happens to have in
    it.

    The origin list is the case that bites. A developer whose `.env` narrows or
    widens `CORS_ALLOWED_ORIGINS` changes what the gate accepts under every test
    that drives the application, and one whose value is malformed makes every
    `create_app()` in the whole suite raise - a failure in tests that have
    nothing to do with the gate, pointing at a file that is not in the
    repository.
    """
    for settings_class in SETTINGS_CLASSES:
        monkeypatch.setitem(settings_class.model_config, "env_file", None)
    monkeypatch.delenv(ORIGIN_VARIABLE, raising=False)
