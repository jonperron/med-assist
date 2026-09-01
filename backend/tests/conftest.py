"""
Test-wide fixtures.

The one thing here exists because the settings classes read a `.env` file as
well as the environment, and a developer's own `.env` would otherwise decide
what the suite tests.
"""

import pytest
from pydantic_settings import BaseSettings

from app.core.access import ACCESS_TOKEN_VARIABLE, AccessTokenConfiguration
from app.core.config import CORSConfiguration, NERModelConfiguration

# Every settings class in the application. Listed rather than discovered so
# that adding one is a deliberate line here: pydantic merges `model_config`
# into each subclass at class creation, so patching `BaseSettings` itself
# reaches none of them.
SETTINGS_CLASSES: tuple[type[BaseSettings], ...] = (
    AccessTokenConfiguration,
    CORSConfiguration,
    NERModelConfiguration,
)


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

    The variable is cleared from the environment too, so a shell that exports it
    does not leak in either; a test that wants one sets it explicitly.
    """
    for settings_class in SETTINGS_CLASSES:
        monkeypatch.setitem(settings_class.model_config, "env_file", None)
    monkeypatch.delenv(ACCESS_TOKEN_VARIABLE, raising=False)
