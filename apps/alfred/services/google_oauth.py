from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Optional

from fastapi import HTTPException
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from oauthlib.oauth2.rfc6749.errors import OAuth2Error
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from alfred.core.config import settings
from alfred.core.database import database_enabled, get_session
from alfred.core.db_models import DEFAULT_USER_KEY, GoogleCredential

# Canonical OAuth scope list - ALWAYS use this exact list for both auth URL and token exchange
# This includes ALL scopes we need for both Gmail and Calendar
# NOTE: We do NOT include gmail.metadata because gmail.readonly is a superset
# that provides all metadata access PLUS the ability to search and read messages
GOOGLE_SCOPES: list[str] = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.readonly",
]

DEFAULT_USER_ID = DEFAULT_USER_KEY
logger = logging.getLogger(__name__)


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


def token_path(user_id: str | None = None) -> Path:
    uid = user_id or DEFAULT_USER_ID
    return _token_store_dir() / f"google_{uid}.json"


def generate_authorization_url(
    state: Optional[str] = None, scopes: Optional[list[str]] = None
) -> tuple[str, str]:
    """Generate OAuth authorization URL.

    IMPORTANT: Always uses GOOGLE_SCOPES regardless of the scopes parameter.
    The scopes parameter is kept for API compatibility but ignored to ensure
    consistency between auth URL generation and token exchange.
    """
    cfg = _client_config()
    # ALWAYS use GOOGLE_SCOPES - ignore the scopes parameter
    flow = Flow.from_client_config(cfg, scopes=GOOGLE_SCOPES)
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
    user_id: str | None, code: str, state: Optional[str] = None, scopes: Optional[list[str]] = None
) -> Credentials:
    """Exchange authorization code for access tokens.

    IMPORTANT: Always uses GOOGLE_SCOPES regardless of the scopes parameter.
    The scopes parameter is kept for API compatibility but ignored to ensure
    consistency with generate_authorization_url().
    """
    cfg = _client_config()
    # ALWAYS use GOOGLE_SCOPES - ignore the scopes parameter
    # This MUST match what was used in generate_authorization_url()
    flow = Flow.from_client_config(cfg, scopes=GOOGLE_SCOPES, state=state)
    if settings.google_redirect_uri:
        flow.redirect_uri = str(settings.google_redirect_uri)

    # Final hardened token exchange logic with enforced canonical & metadata scopes
    canonical_scopes = sorted(set(GOOGLE_SCOPES + ["https://www.googleapis.com/auth/gmail.metadata"]))
    flow = Flow.from_client_config(cfg, scopes=canonical_scopes, state=state)
    if settings.google_redirect_uri:
        flow.redirect_uri = str(settings.google_redirect_uri)

    try:
        flow.fetch_token(code=code)
    except Exception as exc:
        detail = str(exc)
        logger.error("Google OAuth exchange failed with detail: %s", detail)

        if "invalid_grant" in detail or "Bad Request" in detail:
            raise HTTPException(
                status_code=440,
                detail=(
                    "Google authorization code is invalid or expired. "
                    "Please click Connect again to refresh your session."
                ),
            ) from exc

        if "scope" in detail.lower() or "Scope has changed" in detail:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Google scopes changed unexpectedly. "
                    "Please revoke access in your Google Account permissions and reconnect."
                ),
            ) from exc

        raise HTTPException(
            status_code=500,
            detail="Unexpected error during OAuth token exchange. Please retry the connection.",
        ) from exc

    if not flow.credentials or not flow.credentials.token:
        logger.error("OAuth token exchange completed but credentials field is empty")
        raise HTTPException(
            status_code=500,
            detail="OAuth completed but credentials are invalid. Please retry connection.",
        )

    return flow.credentials

    if not flow.credentials:
        logger.error("OAuth token exchange produced no credentials")
        raise HTTPException(
            status_code=400, detail="OAuth token exchange returned no credentials. Please try again."
        )

    return flow.credentials


def persist_credentials(user_id: str | None, creds: Credentials, *, scopes: Optional[list[str]] = None, is_calendar: bool = False) -> None:
    if database_enabled():
        asyncio.run(persist_credentials_async(user_id, creds, scopes=scopes, is_calendar=is_calendar))
    else:
        _persist_credentials_file(user_id, creds)


async def persist_credentials_async(
    user_id: str | None,
    creds: Credentials,
    *,
    scopes: Optional[list[str]] = None,
    is_calendar: bool = False,
) -> None:
    if database_enabled():
        try:
            await _persist_credentials_db(user_id, creds, scopes=scopes, is_calendar=is_calendar)
            return
        except SQLAlchemyError as exc:
            logger.error("Failed to persist Google credentials to database: %s", exc)
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.error("Unexpected error persisting credentials: %s", exc)
    _persist_credentials_file(user_id, creds)


def load_credentials(user_id: str | None = None) -> Credentials | None:
    if database_enabled():
        try:
            return asyncio.run(load_credentials_async(user_id))
        except SQLAlchemyError as exc:
            logger.error("Failed to load Google credentials from database: %s", exc)
        except Exception as exc:  # pragma: no cover
            logger.error("Unexpected error loading credentials: %s", exc)
    return _load_credentials_file(user_id)


async def load_credentials_async(
    user_id: str | None = None,
    *,
    is_calendar: bool = False,
) -> Credentials | None:
    if database_enabled():
        key = user_id or DEFAULT_USER_ID
        async with get_session() as session:
            result = await session.scalar(
                select(GoogleCredential).where(
                    GoogleCredential.user_key == key,
                    GoogleCredential.is_calendar.is_(is_calendar),
                )
            )
        if result is not None:
            data = _prepare_payload(dict(result.credential), scopes=result.scopes)
            try:
                return Credentials.from_authorized_user_info(data)
            except Exception as exc:
                logger.error("Corrupt stored Google credentials for %s: %s", key, exc)
    return _load_credentials_file(user_id)


def _prepare_payload(data: dict[str, Any], *, scopes: Optional[list[str]] = None) -> dict[str, Any]:
    payload = dict(data)
    payload.setdefault("client_id", settings.google_client_id)
    payload.setdefault("client_secret", settings.google_client_secret)
    payload.setdefault("token_uri", "https://oauth2.googleapis.com/token")
    effective_scopes = scopes or payload.get("scopes")
    if not effective_scopes:
        effective_scopes = GOOGLE_SCOPES
    payload["scopes"] = effective_scopes
    return payload


def _persist_credentials_file(user_id: str | None, creds: Credentials) -> None:
    p = token_path(user_id)
    p.write_text(creds.to_json())


def _load_credentials_file(user_id: str | None = None) -> Credentials | None:
    p = token_path(user_id)
    if not p.exists():
        return None
    data = _prepare_payload(json.loads(p.read_text()))
    return Credentials.from_authorized_user_info(data)


async def _persist_credentials_db(
    user_id: str | None,
    creds: Credentials,
    *,
    scopes: Optional[list[str]],
    is_calendar: bool,
) -> None:
    payload = _prepare_payload(json.loads(creds.to_json()), scopes=scopes)
    key = user_id or DEFAULT_USER_ID
    async with get_session() as session:
        record = await session.scalar(
            select(GoogleCredential).where(
                GoogleCredential.user_key == key,
                GoogleCredential.is_calendar.is_(is_calendar),
            )
        )
        if record is None:
            record = GoogleCredential(
                user_key=key,
                credential=payload,
                scopes=payload.get("scopes"),
                is_calendar=is_calendar,
            )
            session.add(record)
        else:
            record.credential = payload
            record.scopes = payload.get("scopes")
        await session.commit()


def _extract_scopes_from_flow(flow: Flow) -> set[str]:
    scope_value = getattr(flow.oauth2session, "scope", None)
    if isinstance(scope_value, str):
        return set(scope_value.split())
    if isinstance(scope_value, (list, tuple, set)):
        return set(scope_value)
    return set()
