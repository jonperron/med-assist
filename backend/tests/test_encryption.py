import pytest
from cryptography.fernet import Fernet

from app.db.encryption import ValueCipher


def test_round_trip():
    cipher = ValueCipher(Fernet.generate_key().decode())
    assert (
        cipher.decrypt(cipher.encrypt("Le patient a 42 ans.")) == "Le patient a 42 ans."
    )


def test_ciphertext_does_not_carry_the_plaintext():
    cipher = ValueCipher(Fernet.generate_key().decode())
    assert "patient" not in cipher.encrypt("Le patient a 42 ans.")


def test_generates_an_ephemeral_key_when_none_is_configured(caplog):
    cipher = ValueCipher(None)
    assert cipher.decrypt(cipher.encrypt("value")) == "value"
    assert "ephemeral key" in caplog.text


def test_two_ephemeral_ciphers_cannot_read_each_other():
    assert ValueCipher(None).decrypt(ValueCipher(None).encrypt("value")) is None


def test_rejects_an_invalid_key():
    with pytest.raises(ValueError, match="STORAGE_ENCRYPTION_KEY"):
        ValueCipher("not-a-fernet-key")


def test_decrypting_a_foreign_token_returns_none():
    other = ValueCipher(Fernet.generate_key().decode())
    cipher = ValueCipher(Fernet.generate_key().decode())
    assert cipher.decrypt(other.encrypt("value")) is None


def test_decrypting_garbage_returns_none():
    assert ValueCipher(Fernet.generate_key().decode()).decrypt("garbage") is None
