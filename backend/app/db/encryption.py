"""Symmetric encryption for everything written to storage.

Values reach Redis as Fernet tokens, so a memory dump, a swapped page or a
recycled disk carries ciphertext rather than clinical text. The key comes from
the environment; when none is configured an ephemeral one is generated, which
keeps the guarantee at the cost of losing stored documents across a restart.
"""

import logging
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


class ValueCipher:
    """Encrypts and decrypts stored values with a single Fernet key."""

    def __init__(self, key: Optional[str] = None) -> None:
        if key:
            try:
                self.fernet = Fernet(key.encode("utf-8"))
                logger.info("Storage encryption uses the configured key")
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    "STORAGE_ENCRYPTION_KEY is not a valid Fernet key. Generate "
                    'one with: python -c "from cryptography.fernet import '
                    'Fernet; print(Fernet.generate_key().decode())"'
                ) from exc
        else:
            logger.warning(
                "No STORAGE_ENCRYPTION_KEY configured: using an ephemeral key. "
                "Stored documents become unreadable when the process restarts, "
                "and every worker holds a different key - run a single worker "
                "or configure a key."
            )
            self.fernet = Fernet(Fernet.generate_key())

    def encrypt(self, value: str) -> str:
        """Encrypt a value for storage."""
        return self.fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, token: str) -> Optional[str]:
        """Decrypt a stored value, or None when it was written under another key."""
        try:
            return self.fernet.decrypt(token.encode("utf-8")).decode("utf-8")
        except InvalidToken:
            # A rotated or ephemeral key leaves unreadable values behind. They
            # expire on their own, so treat them as absent rather than failing.
            logger.warning("Discarding a stored value that this key cannot decrypt")
            return None
