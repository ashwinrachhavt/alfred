from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from alfred.connectors.google_calendar_connector import GoogleCalendarConnector
from alfred.services.google_oauth import (
    exchange_code_for_tokens,
    generate_authorization_url,
    load_credentials_async,
    persist_credentials_async,
)

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]

router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/auth_url")
def calendar_auth_url(state: str | None = Query(default=None)):
    url, st = generate_authorization_url(state, scopes=CALENDAR_SCOPES)
    return {"authorization_url": url, "state": st}


@router.get("/oauth/callback")
async def calendar_oauth_callback(code: str, state: str | None = None):
    creds = exchange_code_for_tokens(
        user_id=None, code=code, state=state, scopes=CALENDAR_SCOPES
    )
    await persist_credentials_async(None, creds, scopes=CALENDAR_SCOPES, is_calendar=True)
    return {"ok": True}


@router.get("/calendars")
async def list_calendars():
    creds = await load_credentials_async(is_calendar=True)
    if creds is None:
        raise HTTPException(404, "No credentials found; authorize via /api/calendar/auth_url")
    connector = GoogleCalendarConnector(
        creds,
        user_id=None,
        on_credentials_refreshed=lambda c: persist_credentials_async(
            None, c, scopes=CALENDAR_SCOPES, is_calendar=True
        ),
    )
    calendars, err = await connector.get_calendars()
    if err:
        raise HTTPException(400, err)
    return {"items": calendars}


@router.get("/events")
async def list_events(start_date: str, end_date: str, max_results: int = 2500):
    creds = await load_credentials_async(is_calendar=True)
    if creds is None:
        raise HTTPException(404, "No credentials found; authorize via /api/calendar/auth_url")
    connector = GoogleCalendarConnector(
        creds,
        user_id=None,
        on_credentials_refreshed=lambda c: persist_credentials_async(
            None, c, scopes=CALENDAR_SCOPES, is_calendar=True
        ),
    )
    events, err = await connector.get_all_primary_calendar_events(
        start_date=start_date, end_date=end_date, max_results=max_results
    )
    if err:
        raise HTTPException(400, err)
    return {"items": events}
