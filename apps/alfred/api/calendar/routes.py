from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from alfred.connectors.google_calendar_connector import GoogleCalendarConnector
from alfred.services.google_oauth import (
    exchange_code_for_tokens,
    generate_authorization_url,
    load_credentials,
    persist_credentials,
)

CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar.events"]
CALENDAR_TOKEN_NAMESPACE = "calendar"


class ReminderInput(BaseModel):
    method: str
    minutes: int


class CalendarEventCreate(BaseModel):
    summary: str = Field(..., min_length=1)
    start: datetime
    timezone: str | None = None
    attendees: list[str] | None = None
    description: str | None = None
    location: str | None = None
    reminders: list[ReminderInput] | None = None


router = APIRouter(prefix="/api/calendar", tags=["calendar"])


@router.get("/auth_url")
def calendar_auth_url(state: str | None = Query(default=None)):
    url, st = generate_authorization_url(state, scopes=CALENDAR_SCOPES)
    return {"authorization_url": url, "state": st}


@router.get("/oauth/callback")
def calendar_oauth_callback(code: str, state: str | None = None):
    exchange_code_for_tokens(
        user_id=None,
        code=code,
        state=state,
        scopes=CALENDAR_SCOPES,
        namespace=CALENDAR_TOKEN_NAMESPACE,
    )
    return {"ok": True}


@router.get("/calendars")
async def list_calendars():
    creds = load_credentials(namespace=CALENDAR_TOKEN_NAMESPACE)
    if creds is None:
        raise HTTPException(404, "No credentials found; authorize via /api/calendar/auth_url")
    connector = GoogleCalendarConnector(
        creds,
        user_id=None,
        on_credentials_refreshed=lambda c: persist_credentials(
            None, c, namespace=CALENDAR_TOKEN_NAMESPACE
        ),
    )
    calendars, err = await connector.get_calendars()
    if err:
        raise HTTPException(400, err)
    return {"items": calendars}


@router.get("/events")
async def list_events(start_date: str, end_date: str, max_results: int = 2500):
    creds = load_credentials(namespace=CALENDAR_TOKEN_NAMESPACE)
    if creds is None:
        raise HTTPException(404, "No credentials found; authorize via /api/calendar/auth_url")
    connector = GoogleCalendarConnector(
        creds,
        user_id=None,
        on_credentials_refreshed=lambda c: persist_credentials(
            None, c, namespace=CALENDAR_TOKEN_NAMESPACE
        ),
    )
    events, err = await connector.get_all_primary_calendar_events(
        start_date=start_date, end_date=end_date, max_results=max_results
    )
    if err:
        raise HTTPException(400, err)
    return {"items": events}


@router.post("/events")
async def create_event(payload: CalendarEventCreate) -> dict[str, Any]:
    creds = load_credentials(namespace=CALENDAR_TOKEN_NAMESPACE)
    if creds is None:
        raise HTTPException(404, "No credentials found; authorize via /api/calendar/auth_url")

    connector = GoogleCalendarConnector(
        creds,
        user_id=None,
        on_credentials_refreshed=lambda c: persist_credentials(
            None, c, namespace=CALENDAR_TOKEN_NAMESPACE
        ),
    )

    try:
        result = await connector.create_event(
            summary=payload.summary,
            start=payload.start,
            timezone=payload.timezone,
            attendees=[str(email) for email in payload.attendees] if payload.attendees else None,
            description=payload.description,
            location=payload.location,
            reminders=[rem.model_dump() for rem in payload.reminders]
            if payload.reminders
            else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    return result
