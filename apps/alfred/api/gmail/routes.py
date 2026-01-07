from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse

from alfred.connectors.google_gmail_connector import GoogleGmailConnector
from alfred.core.settings import settings
from alfred.core.utils import clamp_int
from alfred.services.gmail import GmailService
from alfred.services.google_oauth import (
    generate_authorization_url,
    load_credentials,
    persist_credentials,
)
from alfred.services.google_oauth_flow import complete_google_oauth
from alfred.services.oauth_callback_page import render_oauth_callback_page
from alfred.services.oauth_state import save_oauth_state

router = APIRouter(prefix="/api/gmail", tags=["gmail"])
GMAIL_TOKEN_NAMESPACE = "gmail"
MESSAGE_PREVIEW_HEADERS = ["From", "To", "Subject", "Date"]


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
    save_oauth_state(st, scopes=settings.google_scopes, namespaces=[GMAIL_TOKEN_NAMESPACE])
    return {"authorization_url": url, "state": st}


@router.get("/oauth/callback")
def gmail_oauth_callback(
    code: str,
    state: str | None = None,
    json: bool = Query(default=False),
):
    try:
        result = complete_google_oauth(
            code=code,
            state=state,
            fallback_scopes=settings.google_scopes,
            fallback_namespaces=[GMAIL_TOKEN_NAMESPACE],
            user_id=None,
        )
    except Exception as exc:
        if json:
            raise
        return HTMLResponse(
            content=render_oauth_callback_page(ok=False, message=str(exc)),
            status_code=400,
        )

    if json:
        return result

    return HTMLResponse(
        content=render_oauth_callback_page(ok=True, message="You can return to Alfred."),
        status_code=200,
    )


@router.get("/profile")
async def gmail_profile():
    creds = load_credentials(namespace=GMAIL_TOKEN_NAMESPACE)
    if creds is None:
        raise HTTPException(404, "No credentials found; authorize via /api/google/auth_url")
    connector = GoogleGmailConnector(
        creds,
        user_id=None,
        on_credentials_refreshed=lambda c: persist_credentials(
            None, c, namespace=GMAIL_TOKEN_NAMESPACE
        ),
    )
    profile, err = await connector.get_user_profile()
    if err:
        raise HTTPException(400, err)
    return profile


@router.get("/messages")
async def gmail_messages(
    query: str = Query(default=""),
    max_results: int = Query(default=20, ge=1, le=50),
    include_spam_trash: bool = Query(default=False),
) -> dict[str, object]:
    """Return message previews for the connected Gmail account."""

    creds = load_credentials(namespace=GMAIL_TOKEN_NAMESPACE)
    if creds is None:
        raise HTTPException(404, "No credentials found; authorize via /api/google/auth_url")

    limit = clamp_int(max_results, lo=1, hi=25)
    connector = GoogleGmailConnector(
        creds,
        user_id=None,
        on_credentials_refreshed=lambda c: persist_credentials(
            None, c, namespace=GMAIL_TOKEN_NAMESPACE
        ),
    )

    messages, err = await connector.get_messages_list(
        max_results=limit,
        query=query,
        include_spam_trash=include_spam_trash,
    )
    if err:
        raise HTTPException(status_code=502, detail=err)

    items: list[dict[str, object]] = []
    for msg in messages:
        msg_id = msg.get("id")
        if not isinstance(msg_id, str) or not msg_id:
            continue

        meta, meta_err = await connector.get_message_metadata(
            msg_id,
            metadata_headers=MESSAGE_PREVIEW_HEADERS,
        )
        if meta_err:
            continue

        headers = GmailService.parse_headers(meta)
        items.append(
            {
                "id": meta.get("id"),
                "thread_id": meta.get("threadId"),
                "snippet": meta.get("snippet"),
                "internal_date": meta.get("internalDate"),
                "label_ids": meta.get("labelIds") or [],
                "headers": {
                    "From": headers.get("From"),
                    "To": headers.get("To"),
                    "Subject": headers.get("Subject"),
                    "Date": headers.get("Date"),
                },
            }
        )

    return {"items": items, "count": len(items), "max_results": limit}


@router.get("/messages/{message_id}")
async def gmail_message(message_id: str) -> dict[str, object]:
    """Return parsed details for a single message."""

    creds = load_credentials(namespace=GMAIL_TOKEN_NAMESPACE)
    if creds is None:
        raise HTTPException(404, "No credentials found; authorize via /api/google/auth_url")

    connector = GoogleGmailConnector(
        creds,
        user_id=None,
        on_credentials_refreshed=lambda c: persist_credentials(
            None, c, namespace=GMAIL_TOKEN_NAMESPACE
        ),
    )

    message, err = await connector.get_message_details(message_id)
    if err:
        raise HTTPException(status_code=502, detail=err)

    headers = GmailService.parse_headers(message)
    body = GmailService.extract_plaintext(message)
    return {
        "id": message.get("id"),
        "thread_id": message.get("threadId"),
        "snippet": message.get("snippet"),
        "internal_date": message.get("internalDate"),
        "label_ids": message.get("labelIds") or [],
        "headers": headers,
        "body": body,
        "attachments": GmailService.list_attachments_from_message(message),
    }
