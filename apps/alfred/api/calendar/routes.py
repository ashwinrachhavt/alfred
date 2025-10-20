from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from alfred.connectors.google_calendar_connector import GoogleCalendarConnector
from alfred.services.google_oauth import (
    exchange_code_for_tokens,
    generate_authorization_url,
    load_credentials,
    persist_credentials,
)

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/auth_url")
def calendar_auth_url(state: str | None = Query(default=None)):
    url, st = generate_authorization_url(state, scopes=CALENDAR_SCOPES)
    return {"authorization_url": url, "state": st}


@router.get("/oauth/callback")
def calendar_oauth_callback(code: str, state: str | None = None):
    exchange_code_for_tokens(user_id=None, code=code, state=state, scopes=CALENDAR_SCOPES)
    return {"ok": True}


@router.get("/calendars")
async def list_calendars():
    creds = load_credentials()
    if creds is None:
        raise HTTPException(404, "No credentials found; authorize via /api/calendar/auth_url")
    connector = GoogleCalendarConnector(
        creds, user_id=None, on_credentials_refreshed=lambda c: persist_credentials(None, c)
    )
    calendars, err = await connector.get_calendars()
    if err:
        raise HTTPException(400, err)
    return {"items": calendars}


@router.get("/events")
async def list_events(start_date: str, end_date: str, max_results: int = 2500):
    creds = load_credentials()
    if creds is None:
        raise HTTPException(404, "No credentials found; authorize via /api/calendar/auth_url")
    connector = GoogleCalendarConnector(
        creds, user_id=None, on_credentials_refreshed=lambda c: persist_credentials(None, c)
    )
    events, err = await connector.get_all_primary_calendar_events(
        start_date=start_date, end_date=end_date, max_results=max_results
    )
    if err:
        raise HTTPException(400, err)
    return {"items": events}
