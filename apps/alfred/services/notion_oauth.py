"""Notion OAuth helpers (authorize URL, token exchange, encrypted local storage)."""

from __future__ import annotations

import base64
import json
import secrets
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from alfred.core.crypto import decrypt_json, encrypt_json
from alfred.core.exceptions import ConfigurationError
from alfred.core.settings import settings

NOTION_AUTHORIZE_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"

_TOKEN_PREFIX = "notion_"
_TOKEN_SUFFIX = ".token.json"


def _token_store_dir() -> Path:
    d = Path(settings.token_store_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def token_path(workspace_id: str) -> Path:
    wid = (workspace_id or "").strip()
    if not wid:
        raise ValueError("workspace_id is required")
    return _token_store_dir() / f"{_TOKEN_PREFIX}{wid}{_TOKEN_SUFFIX}"


def is_notion_oauth_configured() -> bool:
    return bool(
        settings.notion_client_id and settings.notion_client_secret and settings.notion_redirect_uri
    )


def _ensure_notion_oauth_configured() -> None:
    if not is_notion_oauth_configured():
        raise ConfigurationError(
            "Notion OAuth is not configured. Set NOTION_CLIENT_ID, NOTION_CLIENT_SECRET, and NOTION_REDIRECT_URI."
        )


def generate_authorization_url(*, state: str | None = None, owner: str = "user") -> tuple[str, str]:
    """Generate a Notion OAuth authorize URL.

    Notion OAuth is scope-less; permissions are configured on the integration in Notion.
    """

    _ensure_notion_oauth_configured()

    st = state or secrets.token_urlsafe(32)
    params = {
        "client_id": settings.notion_client_id,
        "response_type": "code",
        "owner": owner,
        "redirect_uri": str(settings.notion_redirect_uri),
        "state": st,
    }
    return f"{NOTION_AUTHORIZE_URL}?{urlencode(params)}", st


def exchange_code_for_token(*, code: str) -> dict[str, Any]:
    """Exchange a Notion OAuth code for an access token."""

    _ensure_notion_oauth_configured()
    assert settings.notion_client_id is not None  # for type-checkers
    assert settings.notion_client_secret is not None
    assert settings.notion_redirect_uri is not None

    raw_secret = settings.notion_client_secret.get_secret_value()
    basic = base64.b64encode(f"{settings.notion_client_id}:{raw_secret}".encode()).decode(
        "ascii"
    )

    headers = {
        "Authorization": f"Basic {basic}",
        "Content-Type": "application/json",
    }

    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": str(settings.notion_redirect_uri),
    }

    with httpx.Client(timeout=30) as client:
        resp = client.post(NOTION_TOKEN_URL, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict):
            raise RuntimeError("Unexpected Notion token response")
        return data


def persist_oauth_token(token: dict[str, Any]) -> dict[str, Any]:
    """Persist a Notion OAuth token response encrypted on disk.

    Returns a small workspace summary (safe to return to clients).
    """

    workspace_id = (token.get("workspace_id") or "").strip()
    if not workspace_id:
        raise ValueError("Notion token response missing workspace_id")

    record = {
        "created_at": datetime.now(UTC).isoformat(),
        "token": token,
    }
    encrypted = encrypt_json(record, aad=workspace_id.encode("utf-8"))
    token_path(workspace_id).write_text(json.dumps(encrypted, ensure_ascii=False))

    return {
        "workspace_id": workspace_id,
        "workspace_name": token.get("workspace_name"),
        "workspace_icon": token.get("workspace_icon"),
        "bot_id": token.get("bot_id"),
        "owner": token.get("owner"),
    }


def load_oauth_token(workspace_id: str) -> dict[str, Any]:
    """Load and decrypt the stored Notion OAuth token record."""

    path = token_path(workspace_id)
    if not path.exists():
        raise FileNotFoundError(f"No stored Notion token for workspace {workspace_id}")

    encrypted = json.loads(path.read_text())
    if not isinstance(encrypted, dict):
        raise ValueError("Invalid token file")
    record = decrypt_json(encrypted, aad=workspace_id.encode("utf-8"))
    token = record.get("token")
    if not isinstance(token, dict):
        raise ValueError("Invalid token record")
    return token


def list_connected_workspaces() -> list[dict[str, Any]]:
    """List stored Notion OAuth connections (decrypting each token record)."""

    workspaces: list[dict[str, Any]] = []
    for path in _token_store_dir().glob(f"{_TOKEN_PREFIX}*{_TOKEN_SUFFIX}"):
        name = path.name
        workspace_id = name[len(_TOKEN_PREFIX) : -len(_TOKEN_SUFFIX)]
        try:
            token = load_oauth_token(workspace_id)
        except Exception:
            # Corrupt or non-decryptable token files shouldn't break the whole listing.
            continue
        workspaces.append(
            {
                "workspace_id": workspace_id,
                "workspace_name": token.get("workspace_name"),
                "workspace_icon": token.get("workspace_icon"),
                "bot_id": token.get("bot_id"),
                "owner": token.get("owner"),
            }
        )
    return workspaces


def revoke_oauth_token(workspace_id: str) -> bool:
    """Delete a stored Notion OAuth token from disk."""

    path = token_path(workspace_id)
    if not path.exists():
        return False
    path.unlink()
    return True


__all__ = [
    "exchange_code_for_token",
    "generate_authorization_url",
    "is_notion_oauth_configured",
    "list_connected_workspaces",
    "load_oauth_token",
    "persist_oauth_token",
    "revoke_oauth_token",
    "token_path",
]
