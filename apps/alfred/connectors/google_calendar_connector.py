"""
Google Calendar Connector Module | Google OAuth Credentials | Google Calendar API
"""

import inspect
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

import pytz
from dateutil.parser import isoparse
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


class GoogleCalendarConnector:
    """Class for retrieving data from Google Calendar using Google OAuth credentials."""

    def __init__(
        self,
        credentials: Credentials,
        user_id: str | None = None,
        on_credentials_refreshed: Optional[
            Callable[[Credentials], Optional[Awaitable[None]]]
        ] = None,
    ):
        """
        Initialize the GoogleCalendarConnector class.
        Args:
            credentials: Google OAuth Credentials object
            user_id: Optional identifier for the user (for logging/metrics only)
            on_credentials_refreshed: Optional callback invoked after refresh with updated Credentials
        """
        self._credentials = credentials
        self._user_id = user_id
        self._on_refresh = on_credentials_refreshed
        self.service = None

    async def _get_credentials(
        self,
    ) -> Credentials:
        """
        Get valid Google OAuth credentials.
        Returns:
            Google OAuth credentials
        Raises:
            ValueError: If credentials have not been set
            Exception: If credential refresh fails
        """
        if not all(
            [
                self._credentials.client_id,
                self._credentials.client_secret,
                self._credentials.refresh_token,
            ]
        ):
            raise ValueError(
                "Google OAuth credentials (client_id, client_secret, refresh_token) must be set"
            )

        if self._credentials and not self._credentials.expired:
            return self._credentials

        # Create credentials from refresh token
        self._credentials = Credentials(
            token=self._credentials.token,
            refresh_token=self._credentials.refresh_token,
            token_uri=self._credentials.token_uri,
            client_id=self._credentials.client_id,
            client_secret=self._credentials.client_secret,
            scopes=self._credentials.scopes,
            expiry=self._credentials.expiry,
        )

        # Refresh the token if needed
        if self._credentials.expired or not getattr(self._credentials, "valid", False):
            try:
                self._credentials.refresh(Request())
                if self._on_refresh is not None:
                    result = self._on_refresh(self._credentials)
                    if inspect.isawaitable(result):
                        await result  # type: ignore[func-returns-value]
            except Exception as e:
                raise Exception(f"Failed to refresh Google OAuth credentials: {e!s}") from e

        return self._credentials

    async def _get_service(self):
        """Get the Google Calendar service instance using credentials."""
        if self.service:
            return self.service

        try:
            credentials = await self._get_credentials()
            self.service = build("calendar", "v3", credentials=credentials)
            return self.service
        except Exception as e:
            raise Exception(f"Failed to create Google Calendar service: {e!s}") from e

    async def get_calendars(self) -> tuple[list[dict[str, Any]], str | None]:
        """Fetch list of user's calendars using credentials."""
        try:
            service = await self._get_service()
            calendars_result = service.calendarList().list().execute()
            calendars = calendars_result.get("items", [])

            formatted_calendars = []
            for calendar in calendars:
                formatted_calendars.append(
                    {
                        "id": calendar.get("id"),
                        "summary": calendar.get("summary"),
                        "description": calendar.get("description", ""),
                        "primary": calendar.get("primary", False),
                        "accessRole": calendar.get("accessRole"),
                        "timeZone": calendar.get("timeZone"),
                    }
                )

            return formatted_calendars, None

        except Exception as e:
            return [], f"Error fetching calendars: {e!s}"

    async def get_all_primary_calendar_events(
        self,
        start_date: str,
        end_date: str,
        max_results: int = 2500,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Fetch events from the primary calendar using credentials."""
        try:
            service = await self._get_service()

            dt_start = isoparse(start_date)
            dt_end = isoparse(end_date)

            if dt_start.tzinfo is None:
                dt_start = dt_start.replace(tzinfo=pytz.UTC)
            else:
                dt_start = dt_start.astimezone(pytz.UTC)

            if dt_end.tzinfo is None:
                dt_end = dt_end.replace(tzinfo=pytz.UTC)
            else:
                dt_end = dt_end.astimezone(pytz.UTC)

            if dt_start >= dt_end:
                return [], (
                    f"start_date ({dt_start.isoformat()}) must be strictly before "
                    f"end_date ({dt_end.isoformat()})."
                )

            time_min = dt_start.isoformat().replace("+00:00", "Z")
            time_max = dt_end.isoformat().replace("+00:00", "Z")

            events_result = (
                service.events()
                .list(
                    calendarId="primary",
                    maxResults=max_results,
                    singleEvents=True,
                    orderBy="startTime",
                    timeMin=time_min,
                    timeMax=time_max,
                )
                .execute()
            )

            events = events_result.get("items", [])

            if not events:
                return [], "No events found in the specified date range."

            return events, None

        except Exception as e:
            return [], f"Error fetching events: {e!s}"

    def format_event_to_markdown(self, event: dict[str, Any]) -> str:
        """Format a Google Calendar event to markdown."""
        summary = event.get("summary", "No Title")
        description = event.get("description", "")
        location = event.get("location", "")
        calendar_id = event.get("calendarId", "")
        start = event.get("start", {})
        end = event.get("end", {})

        start_time = start.get("dateTime") or start.get("date", "")
        end_time = end.get("dateTime") or end.get("date", "")

        if start_time:
            try:
                if "T" in start_time:
                    start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
                    start_formatted = start_dt.strftime("%Y-%m-%d %H:%M")
                else:
                    start_formatted = start_time
            except Exception:
                start_formatted = start_time
        else:
            start_formatted = "Unknown"

        if end_time:
            try:
                if "T" in end_time:
                    end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
                    end_formatted = end_dt.strftime("%Y-%m-%d %H:%M")
                else:
                    end_formatted = end_time
            except Exception:
                end_formatted = end_time
        else:
            end_formatted = "Unknown"
        attendees = event.get("attendees", [])
        attendee_list = []
        for attendee in attendees:
            email = attendee.get("email", "")
            display_name = attendee.get("displayName", email)
            response_status = attendee.get("responseStatus", "")
            attendee_list.append(f"- {display_name} ({response_status})")
        markdown_content = f"# {summary}\n\n"
        markdown_content += f"**Start:** {start_formatted}\n"
        markdown_content += f"**End:** {end_formatted}\n"
        if location:
            markdown_content += f"**Location:** {location}\n"
        if calendar_id:
            markdown_content += f"**Calendar:** {calendar_id}\n"
        markdown_content += "\n"
        if description:
            markdown_content += f"## Description\n\n{description}\n\n"
        if attendee_list:
            markdown_content += "## Attendees\n\n"
            markdown_content += "\n".join(attendee_list)
            markdown_content += "\n\n"
        markdown_content += "## Event Details\n\n"
        markdown_content += f"- **Event ID:** {event.get('id', 'Unknown')}\n"
        markdown_content += f"- **Created:** {event.get('created', 'Unknown')}\n"
        markdown_content += f"- **Updated:** {event.get('updated', 'Unknown')}\n"

        if event.get("recurringEventId"):
            markdown_content += f"- **Recurring Event ID:** {event.get('recurringEventId')}\n"

        return markdown_content
