"""The shipped defaults are the privacy posture, so they are asserted."""

# pylint: disable=W0621
import pytest

from app.core.config import PrivacyConfiguration


@pytest.fixture
def shipped_defaults(monkeypatch):
    # Read neither the environment nor a local .env: this is about what the
    # code ships, not about what this machine happens to be configured for.
    monkeypatch.delenv("STORE_DOCUMENT_TEXT", raising=False)
    return PrivacyConfiguration(_env_file=None)


def test_document_text_is_not_stored_by_default(shipped_defaults):
    assert shipped_defaults.store_document_text is False


def test_a_deployment_can_opt_into_keeping_the_text(monkeypatch):
    monkeypatch.setenv("STORE_DOCUMENT_TEXT", "true")

    assert PrivacyConfiguration(_env_file=None).store_document_text is True
