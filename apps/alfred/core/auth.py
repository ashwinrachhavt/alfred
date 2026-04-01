"""Clerk JWT authentication for FastAPI.

Verifies JWTs issued by Clerk using JWKS (public key verification).
When Clerk env vars are not configured, auth is disabled and a dummy user
is returned to keep local development frictionless.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass

import jwt
from fastapi import Cookie, Depends, HTTPException, Request
from jwt import PyJWKClient

from alfred.core.settings import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# User payload returned by auth dependencies
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class AuthUser:
    """Minimal user context extracted from a verified Clerk JWT."""

    user_id: str


# ---------------------------------------------------------------------------
# Singleton JWKS client (lazily initialised)
# ---------------------------------------------------------------------------

_jwk_client: PyJWKClient | None = None
_clerk_issuer: str | None = None
_auth_disabled: bool | None = None


def _derive_jwks_url(publishable_key: str) -> tuple[str, str]:
    """Derive the JWKS URL and issuer from a Clerk publishable key.

    Clerk publishable keys are formatted as ``pk_test_<base64>`` or
    ``pk_live_<base64>`` where the base64-decoded value is
    ``<instance>.clerk.accounts.dev$``.

    Returns:
        (jwks_url, issuer) tuple
    """
    # Strip the pk_test_ / pk_live_ prefix
    parts = publishable_key.split("_", 2)
    if len(parts) < 3:
        raise ValueError(f"Invalid Clerk publishable key format: {publishable_key!r}")
    encoded = parts[2]

    # Decode – Clerk uses standard base64 with trailing '$' in the plaintext
    decoded = base64.b64decode(encoded + "==").decode("utf-8").rstrip("$")

    jwks_url = f"https://{decoded}/.well-known/jwks.json"
    issuer = f"https://{decoded}"
    return jwks_url, issuer


def _init_auth() -> tuple[bool, PyJWKClient | None, str | None]:
    """Initialise auth state from settings (called once, lazily)."""
    global _jwk_client, _clerk_issuer, _auth_disabled  # noqa: PLW0603

    if _auth_disabled is not None:
        return _auth_disabled, _jwk_client, _clerk_issuer

    settings = get_settings()

    has_secret = settings.clerk_secret_key is not None
    has_pk = settings.clerk_publishable_key is not None

    if not has_secret and not has_pk:
        logger.warning(
            "Clerk auth is DISABLED: CLERK_SECRET_KEY and CLERK_PUBLISHABLE_KEY "
            "are not set. All requests will use a dummy dev user."
        )
        _auth_disabled = True
        return True, None, None

    # Determine JWKS URL
    jwks_url = settings.clerk_jwks_url
    issuer: str | None = None

    if not jwks_url and has_pk:
        jwks_url, issuer = _derive_jwks_url(settings.clerk_publishable_key)  # type: ignore[arg-type]

    if not jwks_url:
        logger.warning(
            "Clerk auth is DISABLED: could not determine JWKS URL. "
            "Set CLERK_JWKS_URL or CLERK_PUBLISHABLE_KEY."
        )
        _auth_disabled = True
        return True, None, None

    _jwk_client = PyJWKClient(jwks_url, cache_keys=True)
    _clerk_issuer = issuer
    _auth_disabled = False
    logger.info("Clerk JWT auth enabled (JWKS: %s)", jwks_url)
    return False, _jwk_client, _clerk_issuer


# ---------------------------------------------------------------------------
# Token verification
# ---------------------------------------------------------------------------

_DEV_USER = AuthUser(user_id="dev-user")


def verify_clerk_jwt(token: str) -> dict:
    """Verify a Clerk JWT and return the decoded payload.

    Raises ``jwt.PyJWTError`` on any verification failure.
    """
    disabled, client, issuer = _init_auth()
    if disabled or client is None:
        raise RuntimeError("Auth is disabled; should not call verify_clerk_jwt")

    signing_key = client.get_signing_key_from_jwt(token)

    decode_options: dict = {
        "verify_exp": True,
    }
    decode_kwargs: dict = {
        "jwt": token,
        "key": signing_key.key,
        "algorithms": ["RS256"],
        "options": decode_options,
    }

    if issuer:
        decode_kwargs["issuer"] = issuer

    return jwt.decode(**decode_kwargs)


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


def _extract_token(request: Request) -> str | None:
    """Extract JWT from __session cookie or Authorization header."""
    # 1. Cookie (browser requests via Next.js rewrite)
    token = request.cookies.get("__session")
    if token:
        return token

    # 2. Authorization: Bearer <token> (API clients, mobile)
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()

    return None


async def get_current_user(request: Request) -> AuthUser:
    """FastAPI dependency that requires a valid Clerk JWT.

    When Clerk is not configured, returns a dummy dev user.
    """
    disabled, _, _ = _init_auth()
    if disabled:
        return _DEV_USER

    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    try:
        payload = verify_clerk_jwt(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.PyJWTError as exc:
        logger.debug("JWT verification failed: %s", exc)
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing subject claim")

    return AuthUser(user_id=user_id)


async def optional_auth(request: Request) -> AuthUser | None:
    """FastAPI dependency that returns None instead of raising 401.

    Useful for endpoints that work with or without authentication.
    """
    disabled, _, _ = _init_auth()
    if disabled:
        return _DEV_USER

    token = _extract_token(request)
    if not token:
        return None

    try:
        payload = verify_clerk_jwt(token)
    except jwt.PyJWTError:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    return AuthUser(user_id=user_id)
