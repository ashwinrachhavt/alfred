from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from alfred.connectors.google_gmail_connector import GoogleGmailConnector
from alfred.services.google_oauth import (
    exchange_code_for_tokens,
    generate_authorization_url,
    load_credentials,
    persist_credentials,
)

router = APIRouter(prefix="/api/v1/gmail", tags=["gmail"])


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
        raise HTTPException(404, "No credentials found; authorize via /api/v1/gmail/auth_url")
    connector = GoogleGmailConnector(
        creds, user_id=None, on_credentials_refreshed=lambda c: persist_credentials(None, c)
    )
    profile, err = await connector.get_user_profile()
    if err:
        raise HTTPException(400, err)
    return profile
