"""Tests for TokenEncryptor."""

from __future__ import annotations

import pytest

from app.services.git.encryption import TokenEncryptor


def test_encrypt_returns_bytes():
    ciphertext = TokenEncryptor.encrypt("my-secret-token")
    assert isinstance(ciphertext, bytes)


def test_roundtrip_preserves_token():
    token = "ghp_test_token_12345"
    ciphertext = TokenEncryptor.encrypt(token)
    assert TokenEncryptor.decrypt(ciphertext) == token


def test_different_encryptions_are_unique():
    token = "same-token"
    first = TokenEncryptor.encrypt(token)
    second = TokenEncryptor.encrypt(token)
    assert first != second


def test_decrypt_raises_on_corrupted_data():
    with pytest.raises(ValueError, match="Failed to decrypt"):
        TokenEncryptor.decrypt(b"not-valid-ciphertext")


def test_uses_generated_key_when_secret_not_set():
    import app.services.git.encryption as enc

    original_fernet = enc._fernet
    original_key = enc.SECRET_KEY
    try:
        enc._fernet = None
        enc.SECRET_KEY = ""  # type: ignore[attr-defined]
        ciphertext = TokenEncryptor.encrypt("token")
        assert isinstance(ciphertext, bytes)
    finally:
        enc._fernet = original_fernet
        enc.SECRET_KEY = original_key  # type: ignore[attr-defined]
