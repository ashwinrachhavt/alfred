from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.responses import Response

from alfred.core.exceptions import ConfigurationError
from alfred.core.settings import settings
from alfred.services.google_oauth import generate_authorization_url, load_credentials, token_path
from alfred.services.google_oauth_flow import complete_google_oauth
from alfred.services.oauth_callback_page import render_oauth_callback_page
from alfred.services.oauth_state import save_oauth_state

router = APIRouter(prefix="/api/google", tags=["google"])

GMAIL_NAMESPACE = "gmail"
CALENDAR_NAMESPACE = "calendar"


def _union_scopes(*, base: list[str], extra: list[str]) -> list[str]:
    out: list[str] = []
    for scope in base:
        if scope not in out:
            out.append(scope)
    for scope in extra:
        if scope not in out:
            out.append(scope)
    return out


def _ensure_oauth_configured() -> None:
    if not (
        settings.google_client_id and settings.google_client_secret and settings.google_redirect_uri
    ):
        raise ConfigurationError(
            "Google OAuth is not configured. Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REDIRECT_URI."
        )


@router.get("/status")
def google_status() -> dict[str, object]:
    """Return Google OAuth configuration + credential presence."""

    configured = bool(
        settings.google_client_id and settings.google_client_secret and settings.google_redirect_uri
    )

    gmail_token = token_path(None, namespace=GMAIL_NAMESPACE)
    calendar_token = token_path(None, namespace=CALENDAR_NAMESPACE)

    gmail_exists = gmail_token.exists()
    calendar_exists = calendar_token.exists()

    try:
        creds = load_credentials(namespace=GMAIL_NAMESPACE) or load_credentials(
            namespace=CALENDAR_NAMESPACE
        )
    except Exception:
        creds = None
    expired = bool(creds.expired) if creds is not None else None
    expiry_iso = None
    if creds is not None and getattr(creds, "expiry", None) is not None:
        expiry_dt: datetime = creds.expiry
        expiry_iso = expiry_dt.astimezone(UTC).isoformat()

    return {
        "configured": configured,
        "gmail_token_present": gmail_exists,
        "calendar_token_present": calendar_exists,
        "expires_at": expiry_iso,
        "expired": expired,
        "scopes": list(getattr(creds, "scopes", []) or []) if creds is not None else [],
    }


@router.get("/auth_url")
def google_auth_url(
    state: str | None = Query(default=None),
) -> dict[str, str]:
    """Generate a Google OAuth URL that enables Gmail + Calendar."""

    _ensure_oauth_configured()

    calendar_scopes = ["https://www.googleapis.com/auth/calendar.events"]
    scopes = _union_scopes(base=settings.google_scopes, extra=calendar_scopes)

    url, st = generate_authorization_url(state=state, scopes=scopes)
    save_oauth_state(st, scopes=scopes, namespaces=[GMAIL_NAMESPACE, CALENDAR_NAMESPACE])
    return {"authorization_url": url, "state": st}


@router.get("/oauth/callback", response_model=None)
def google_oauth_callback(
    code: str,
    state: str | None = None,
    json: bool = Query(default=False),
) -> Response:
    """Handle Google OAuth callback and persist tokens for Gmail + Calendar."""

    calendar_scopes = ["https://www.googleapis.com/auth/calendar.events"]
    scopes = _union_scopes(base=settings.google_scopes, extra=calendar_scopes)

    try:
        result = complete_google_oauth(
            code=code,
            state=state,
            fallback_scopes=scopes,
            fallback_namespaces=[GMAIL_NAMESPACE, CALENDAR_NAMESPACE],
            user_id=None,
        )
    except Exception as exc:
        if json:
            return JSONResponse(
                content={"ok": False, "error": str(exc)},
                status_code=400,
            )
        return HTMLResponse(
            content=render_oauth_callback_page(ok=False, message=str(exc)),
            status_code=400,
        )

    if json:
        return JSONResponse(content=result, status_code=200)

    return HTMLResponse(
        content=render_oauth_callback_page(ok=True, message="You can return to Alfred."),
        status_code=200,
    )


@router.post("/revoke")
def google_revoke() -> dict[str, object]:
    """Delete stored Google tokens (Gmail + Calendar)."""

    removed: list[str] = []
    for namespace in (GMAIL_NAMESPACE, CALENDAR_NAMESPACE):
        path = token_path(None, namespace=namespace)
        try:
            if path.exists():
                path.unlink()
                removed.append(namespace)
        except Exception:
            continue

    return {"ok": True, "removed": removed}
