"""
Google Gmail Connector Module | Google OAuth Credentials | Gmail API
"""

import base64
import re
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Optional

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from alfred.connectors.google_oauth_session import GoogleOAuthSession


class GoogleGmailConnector:
    """Class for retrieving emails from Gmail using Google OAuth credentials."""

    def __init__(
        self,
        credentials: Credentials,
        user_id: str | None = None,
        on_credentials_refreshed: Optional[
            Callable[[Credentials], Optional[Awaitable[None]]]
        ] = None,
    ):
        """Initialize the connector."""
        self._credentials = credentials
        self._user_id = user_id
        self._on_refresh = on_credentials_refreshed
        self._oauth_session = GoogleOAuthSession(
            credentials, on_credentials_refreshed=on_credentials_refreshed
        )
        self.service = None

    async def _get_credentials(
        self,
    ) -> Credentials:
        """Get valid Google OAuth credentials."""
        try:
            self._credentials = await self._oauth_session.get_credentials()
            return self._credentials
        except ValueError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Failed to refresh Google OAuth credentials: {exc!s}") from exc

    async def _get_service(self):
        """Get the Gmail service instance using credentials."""
        if self.service:
            return self.service

        try:
            credentials = await self._get_credentials()
            self.service = build("gmail", "v1", credentials=credentials)
            return self.service
        except Exception as exc:
            raise RuntimeError(f"Failed to create Gmail service: {exc!s}") from exc

    async def get_user_profile(self) -> tuple[dict[str, Any], str | None]:
        """Fetch user's Gmail profile information."""
        try:
            service = await self._get_service()
            profile = service.users().getProfile(userId="me").execute()

            return {
                "email_address": profile.get("emailAddress"),
                "messages_total": profile.get("messagesTotal", 0),
                "threads_total": profile.get("threadsTotal", 0),
                "history_id": profile.get("historyId"),
            }, None

        except Exception as e:
            return {}, f"Error fetching user profile: {e!s}"

    async def get_messages_list(
        self,
        max_results: int = 100,
        query: str = "",
        label_ids: list[str] | None = None,
        include_spam_trash: bool = False,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Fetch list of messages from Gmail."""
        try:
            service = await self._get_service()
            request_params = {
                "userId": "me",
                "maxResults": max_results,
                "includeSpamTrash": include_spam_trash,
            }
            if query:
                request_params["q"] = query
            if label_ids:
                request_params["labelIds"] = label_ids
            result = service.users().messages().list(**request_params).execute()
            messages = result.get("messages", [])
            return messages, None

        except Exception as e:
            return [], f"Error fetching messages list: {e!s}"

    async def get_message_details(self, message_id: str) -> tuple[dict[str, Any], str | None]:
        """Fetch detailed information for a specific message."""
        try:
            service = await self._get_service()
            message = (
                service.users().messages().get(userId="me", id=message_id, format="full").execute()
            )
            return message, None

        except Exception as e:
            return {}, f"Error fetching message details: {e!s}"

    async def get_recent_messages(
        self,
        max_results: int = 50,
        days_back: int = 30,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Fetch recent messages from Gmail within specified days."""
        try:
            cutoff_date = datetime.now() - timedelta(days=days_back)
            date_query = cutoff_date.strftime("%Y/%m/%d")
            query = f"after:{date_query}"
            messages_list, error = await self.get_messages_list(
                max_results=max_results, query=query
            )
            if error:
                return [], error
            detailed_messages = []
            for msg in messages_list:
                message_details, detail_error = await self.get_message_details(msg["id"])
                if detail_error:
                    continue
                detailed_messages.append(message_details)
            return detailed_messages, None

        except Exception as e:
            return [], f"Error fetching recent messages: {e!s}"

    def extract_message_text(self, message: dict[str, Any]) -> str:
        """Extract text content from a Gmail message."""

        def get_message_parts(payload):
            """Recursively extract message parts."""
            parts = []
            if "parts" in payload:
                for part in payload["parts"]:
                    parts.extend(get_message_parts(part))
            else:
                parts.append(payload)
            return parts

        try:
            payload = message.get("payload", {})
            parts = get_message_parts(payload)
            text_content = ""
            for part in parts:
                mime_type = part.get("mimeType", "")
                body = part.get("body", {})
                data = body.get("data", "")
                if mime_type == "text/plain" and data:
                    decoded_data = base64.urlsafe_b64decode(data + "===").decode(
                        "utf-8", errors="ignore"
                    )
                    text_content += decoded_data + "\n"
                elif mime_type == "text/html" and data and not text_content:
                    decoded_data = base64.urlsafe_b64decode(data + "===").decode(
                        "utf-8", errors="ignore"
                    )
                    text_content = re.sub(r"<[^>]+>", "", decoded_data)
            return text_content.strip()

        except Exception as e:
            return f"Error extracting message text: {e!s}"

    def format_message_to_markdown(self, message: dict[str, Any]) -> str:
        """Format a Gmail message to markdown."""
        try:
            message_id = message.get("id", "")
            thread_id = message.get("threadId", "")
            label_ids = message.get("labelIds", [])
            payload = message.get("payload", {})
            headers = payload.get("headers", [])
            header_dict = {}
            for header in headers:
                name = header.get("name", "").lower()
                value = header.get("value", "")
                header_dict[name] = value
            subject = header_dict.get("subject", "No Subject")
            from_email = header_dict.get("from", "Unknown Sender")
            to_email = header_dict.get("to", "Unknown Recipient")
            date_str = header_dict.get("date", "Unknown Date")
            message_text = self.extract_message_text(message)
            markdown_content = f"# {subject}\n\n"
            markdown_content += f"**From:** {from_email}\n"
            markdown_content += f"**To:** {to_email}\n"
            markdown_content += f"**Date:** {date_str}\n"
            if label_ids:
                markdown_content += f"**Labels:** {', '.join(label_ids)}\n"
            markdown_content += "\n"
            if message_text:
                markdown_content += f"## Message Content\n\n{message_text}\n\n"
            markdown_content += "## Message Details\n\n"
            markdown_content += f"- **Message ID:** {message_id}\n"
            markdown_content += f"- **Thread ID:** {thread_id}\n"
            snippet = message.get("snippet", "")
            if snippet:
                markdown_content += f"- **Snippet:** {snippet}\n"
            return markdown_content

        except Exception as e:
            return f"Error formatting message to markdown: {e!s}"
