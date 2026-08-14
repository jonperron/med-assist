"""The shipped defaults are the privacy posture, so they are asserted."""

import pytest

from app.core.config import PrivacyConfiguration


@pytest.fixture
def shipped_defaults(monkeypatch):
    # Read neither the environment nor a local .env: this is about what the
    # code ships, not about what this machine happens to be configured for.
    monkeypatch.delenv("PSEUDONYMIZE_ENTITIES", raising=False)
    monkeypatch.delenv("STORE_DOCUMENT_TEXT", raising=False)
    return PrivacyConfiguration(_env_file=None)


def test_identifiers_are_masked_by_default(shipped_defaults):
    assert shipped_defaults.pseudonymize is True


def test_document_text_is_not_stored_by_default(shipped_defaults):
    assert shipped_defaults.store_document_text is False


def test_a_deployment_can_still_opt_out(monkeypatch):
    monkeypatch.setenv("PSEUDONYMIZE_ENTITIES", "false")

    assert PrivacyConfiguration(_env_file=None).pseudonymize is False
