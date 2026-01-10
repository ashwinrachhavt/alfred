"""Small crypto helpers for token-at-rest encryption.

Alfred stores OAuth tokens on disk for local development and single-tenant
deployments. To avoid persisting access tokens in plaintext, this module
encrypts/decrypts small JSON payloads using AES-256-GCM, deriving a key from
`settings.secret_key`.
"""

from __future__ import annotations

import base64
import json
import os
from hashlib import sha256
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from alfred.core.exceptions import ConfigurationError
from alfred.core.settings import settings

_NONCE_BYTES = 12
_SCHEMA_VERSION = 1


def _derive_key_from_secret(secret: str) -> bytes:
    """Derive a stable 32-byte AES key from an application secret string."""

    if not (secret or "").strip():
        raise ConfigurationError("SECRET_KEY is empty; required for token encryption.")
    return sha256(secret.encode("utf-8")).digest()


def _get_app_key() -> bytes:
    """Return the AES key derived from `settings.secret_key`."""

    if settings.secret_key is None:
        raise ConfigurationError("SECRET_KEY not configured; required for token encryption.")
    return _derive_key_from_secret(settings.secret_key.get_secret_value())


def encrypt_bytes(plaintext: bytes, *, aad: bytes | None = None) -> dict[str, Any]:
    """Encrypt bytes using AES-256-GCM.

    Args:
        plaintext: Raw bytes to encrypt.
        aad: Optional associated data (must match on decrypt).

    Returns:
        JSON-serializable payload containing nonce + ciphertext.
    """

    nonce = os.urandom(_NONCE_BYTES)
    aesgcm = AESGCM(_get_app_key())
    ciphertext = aesgcm.encrypt(nonce, plaintext, aad)
    return {
        "v": _SCHEMA_VERSION,
        "alg": "AES-256-GCM",
        "nonce": base64.urlsafe_b64encode(nonce).decode("ascii"),
        "ciphertext": base64.urlsafe_b64encode(ciphertext).decode("ascii"),
    }


def decrypt_bytes(payload: dict[str, Any], *, aad: bytes | None = None) -> bytes:
    """Decrypt bytes produced by :func:`encrypt_bytes`."""

    if payload.get("v") != _SCHEMA_VERSION:
        raise ValueError("Unsupported encrypted payload version")
    if payload.get("alg") != "AES-256-GCM":
        raise ValueError("Unsupported encryption algorithm")

    nonce_b64 = payload.get("nonce")
    ciphertext_b64 = payload.get("ciphertext")
    if not (isinstance(nonce_b64, str) and isinstance(ciphertext_b64, str)):
        raise ValueError("Invalid encrypted payload shape")

    nonce = base64.urlsafe_b64decode(nonce_b64.encode("ascii"))
    ciphertext = base64.urlsafe_b64decode(ciphertext_b64.encode("ascii"))

    aesgcm = AESGCM(_get_app_key())
    return aesgcm.decrypt(nonce, ciphertext, aad)


def encrypt_json(data: dict[str, Any], *, aad: bytes | None = None) -> dict[str, Any]:
    """Encrypt a JSON object into an AES-GCM envelope."""

    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return encrypt_bytes(raw, aad=aad)


def decrypt_json(payload: dict[str, Any], *, aad: bytes | None = None) -> dict[str, Any]:
    """Decrypt a JSON object produced by :func:`encrypt_json`."""

    raw = decrypt_bytes(payload, aad=aad)
    obj = json.loads(raw.decode("utf-8"))
    if not isinstance(obj, dict):
        raise ValueError("Decrypted payload is not a JSON object")
    return obj


__all__ = [
    "decrypt_bytes",
    "decrypt_json",
    "encrypt_bytes",
    "encrypt_json",
]
