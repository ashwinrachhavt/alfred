from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class PasswordHash:
    salt_hex: str
    digest_hex: str


def hash_password(password: str, *, iterations: int = 120_000) -> PasswordHash:
    """Hash a password for share-link access.

    Uses PBKDF2-HMAC-SHA256 with a per-password random salt.
    """

    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return PasswordHash(salt_hex=salt.hex(), digest_hex=digest.hex())


def verify_password(
    password: str, *, salt_hex: str, digest_hex: str, iterations: int = 120_000
) -> bool:
    """Verify a password against a stored PBKDF2 hash."""

    try:
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except ValueError:
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(actual, expected)

