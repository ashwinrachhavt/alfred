from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query

from alfred.connectors.google_gmail_connector import GoogleGmailConnector
from alfred.services.gmail import GmailService
from alfred.services.google_oauth import (
    exchange_code_for_tokens,
    generate_authorization_url,
    load_credentials_async,
    persist_credentials_async,
)

router = APIRouter(prefix="/api/gmail", tags=["gmail"])


def _truthy(val: str | None) -> bool:
    if val is None:
        return False
    return val.strip().lower() in {"1", "true", "yes", "on"}


@router.get("/status")
def gmail_status():
    enabled = _truthy(os.getenv("ENABLE_GMAIL", "false"))
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "")
    project_id = os.getenv("GOOGLE_PROJECT_ID", "")
    token_dir = os.getenv("TOKEN_STORE_DIR", "")
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
async def gmail_oauth_callback(code: str, state: str | None = None):
    creds = exchange_code_for_tokens(user_id=None, code=code, state=state)
    await persist_credentials_async(None, creds)
    return {"ok": True}


@router.get("/profile")
async def gmail_profile():
    creds = await load_credentials_async()
    if creds is None:
        raise HTTPException(404, "No credentials found; authorize via /api/gmail/auth_url")
    connector = GoogleGmailConnector(
        creds, user_id=None, on_credentials_refreshed=lambda c: persist_credentials_async(None, c)
    )
    profile, err = await connector.get_user_profile()
    if err:
        raise HTTPException(400, err)
    return profile


@router.get("/messages")
async def gmail_messages(
    q: str = Query("", max_length=500),
    max_results: int = Query(20, ge=1, le=100),
    include_body: bool = Query(False),
):
    """Search Gmail messages using the stored OAuth credentials."""

    creds = await load_credentials_async()
    if creds is None:
        raise HTTPException(404, "No credentials found; authorize via /api/google/auth-url")

    connector = GoogleGmailConnector(
        creds, user_id=None, on_credentials_refreshed=lambda c: persist_credentials_async(None, c)
    )

    messages, err = await connector.get_messages_list(max_results=max_results, query=q or "")
    if err:
        raise HTTPException(400, err)

    results = []
    for message_stub in messages:
        detail, detail_err = await connector.get_message_details(message_stub.get("id", ""))
        if detail_err:
            continue
        headers = GmailService.parse_headers(detail)
        item = {
            "id": detail.get("id"),
            "thread_id": detail.get("threadId"),
            "snippet": detail.get("snippet"),
            "subject": headers.get("Subject"),
            "from": headers.get("From"),
            "to": headers.get("To"),
            "date": headers.get("Date"),
        }
        if include_body:
            item["body"] = GmailService.extract_plaintext(detail)
        results.append(item)

    return {"items": results}
