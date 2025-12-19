from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query

from alfred.connectors.google_gmail_connector import GoogleGmailConnector
from alfred.services.google_oauth import (
    exchange_code_for_tokens,
    generate_authorization_url,
    load_credentials,
    persist_credentials,
)

router = APIRouter(prefix="/api/gmail", tags=["gmail"])


def _truthy(val: str | None) -> bool:
    if val is None:
        return False
    return val.strip().lower() in {"1", "true", "yes", "on"}


@router.get("/status")
def gmail_status():
    enabled = _truthy(os.getenv("ENABLE_GMAIL"))
    client_id = (os.getenv("GOOGLE_CLIENT_ID") or "").strip()
    client_secret = (os.getenv("GOOGLE_CLIENT_SECRET") or "").strip()
    redirect_uri = (os.getenv("GOOGLE_REDIRECT_URI") or "").strip()
    project_id = (os.getenv("GOOGLE_PROJECT_ID") or "").strip()
    token_dir = (os.getenv("TOKEN_STORE_DIR") or "").strip()
    configured = all([client_id, client_secret, redirect_uri, project_id])
    token_dir_ready = bool(token_dir)
    deps_ok = True
    ready = enabled and configured and deps_ok and token_dir_ready
    return {
        "enabled": enabled,
        "configured": configured,
        "deps_installed": deps_ok,
        "token_dir_ready": token_dir_ready,
        "ready": ready,
    }


@router.get("/auth_url")
def gmail_auth_url(state: str | None = Query(default=None)):
    url, st = generate_authorization_url(state)
    return {"authorization_url": url, "state": st}


@router.get("/oauth/callback")
def gmail_oauth_callback(code: str, state: str | None = None):
    exchange_code_for_tokens(user_id=None, code=code, state=state)
    return {"ok": True}


@router.get("/profile")
async def gmail_profile():
    creds = load_credentials()
    if creds is None:
        raise HTTPException(404, "No credentials found; authorize via /api/gmail/auth_url")
    connector = GoogleGmailConnector(
        creds, user_id=None, on_credentials_refreshed=lambda c: persist_credentials(None, c)
    )
    profile, err = await connector.get_user_profile()
    if err:
        raise HTTPException(400, err)
    return profile
