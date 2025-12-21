from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow

from alfred.core.settings import settings

DEFAULT_USER_ID = "default"
DEFAULT_NAMESPACE = None


def _client_config() -> dict[str, Any]:
    if not (settings.google_client_id and settings.google_client_secret):
        raise RuntimeError("GOOGLE_CLIENT_ID/GOOGLE_CLIENT_SECRET not configured")
    redirect_uris = []
    if settings.google_redirect_uri:
        redirect_uris = [str(settings.google_redirect_uri)]
    return {
        "web": {
            "client_id": settings.google_client_id,
            "project_id": settings.google_project_id or "alfred-google",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_secret": settings.google_client_secret,
            "redirect_uris": redirect_uris,
        }
    }


def _token_store_dir() -> Path:
    d = Path(settings.token_store_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


def token_path(user_id: str | None = None, *, namespace: str | None = DEFAULT_NAMESPACE) -> Path:
    uid = user_id or DEFAULT_USER_ID
    ns = (namespace or "").strip().lower()
    if ns:
        return _token_store_dir() / f"google_{ns}_{uid}.json"
    return _token_store_dir() / f"google_{uid}.json"


def generate_authorization_url(
    state: Optional[str] = None, scopes: Optional[list[str]] = None
) -> tuple[str, str]:
    cfg = _client_config()
    flow = Flow.from_client_config(cfg, scopes=scopes or settings.google_scopes)
    if settings.google_redirect_uri:
        flow.redirect_uri = str(settings.google_redirect_uri)
    url, st = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return url, st


def exchange_code_for_tokens(
    user_id: str | None,
    code: str,
    state: Optional[str] = None,
    scopes: Optional[list[str]] = None,
    *,
    namespace: str | None = DEFAULT_NAMESPACE,
) -> Credentials:
    cfg = _client_config()
    flow = Flow.from_client_config(cfg, scopes=scopes or settings.google_scopes, state=state)
    if settings.google_redirect_uri:
        flow.redirect_uri = str(settings.google_redirect_uri)
    flow.fetch_token(code=code)
    creds = flow.credentials
    persist_credentials(user_id, creds, namespace=namespace)
    return creds


def persist_credentials(
    user_id: str | None,
    creds: Credentials,
    *,
    namespace: str | None = DEFAULT_NAMESPACE,
) -> None:
    p = token_path(user_id, namespace=namespace)
    p.write_text(creds.to_json())


def load_credentials(
    user_id: str | None = None,
    *,
    namespace: str | None = DEFAULT_NAMESPACE,
) -> Credentials | None:
    p = token_path(user_id, namespace=namespace)
    legacy = token_path(user_id, namespace=None)
    path = p if p.exists() else legacy
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    # Ensure client fields are present (some dumps omit them)
    data.setdefault("client_id", settings.google_client_id)
    data.setdefault("client_secret", settings.google_client_secret)
    data.setdefault("token_uri", "https://oauth2.googleapis.com/token")
    # Scopes may be a string or list
    if "scopes" not in data or not data["scopes"]:
        data["scopes"] = settings.google_scopes
    return Credentials.from_authorized_user_info(data)


__all__ = [
    "DEFAULT_NAMESPACE",
    "DEFAULT_USER_ID",
    "exchange_code_for_tokens",
    "generate_authorization_url",
    "load_credentials",
    "persist_credentials",
    "token_path",
]
