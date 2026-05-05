"""Token encryption and decryption using Fernet symmetric encryption."""

from __future__ import annotations

import logging

from cryptography.fernet import Fernet, InvalidToken

from app.config import SECRET_KEY

_log = logging.getLogger(__name__)

_fernet: Fernet | None = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        if not SECRET_KEY:
            _log.warning(
                "DUCKBRICKS_SECRET_KEY is not set. "
                "A temporary key will be used — tokens will not survive restarts."
            )
            key = Fernet.generate_key()
        else:
            key = SECRET_KEY.encode()
        _fernet = Fernet(key)
    return _fernet


class TokenEncryptor:
    """Encrypts and decrypts credential tokens stored in the database."""

    @staticmethod
    def encrypt(token: str) -> bytes:
        """Encrypt a plaintext token and return the ciphertext bytes."""
        ciphertext: bytes = _get_fernet().encrypt(token.encode())
        return ciphertext

    @staticmethod
    def decrypt(ciphertext: bytes) -> str:
        """Decrypt ciphertext bytes and return the plaintext token."""
        try:
            plaintext: str = _get_fernet().decrypt(ciphertext).decode()
            return plaintext
        except InvalidToken as exc:
            raise ValueError("Failed to decrypt token — invalid key or corrupted data.") from exc
