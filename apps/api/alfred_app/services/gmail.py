from __future__ import annotations

import base64
import json
import pathlib
import time
from typing import Optional

import logging
from fastapi import HTTPException

try:
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from google_auth_oauthlib.flow import Flow
    from google.auth.transport.requests import Request
except Exception:  # pragma: no cover - optional import for non-gmail dev
    Credentials = object  # type: ignore
    Flow = object  # type: ignore
    Request = object  # type: ignore
    build = lambda *_, **__: None  # type: ignore

from itsdangerous import URLSafeSerializer

from alfred_app.core.config import settings

logger = logging.getLogger(__name__)

AUTH_URI = "https://accounts.google.com/o/oauth2/auth"
TOKEN_URI = "https://oauth2.googleapis.com/token"


def _client_config():
    if not (
        settings.google_client_id
        and settings.google_client_secret
        and settings.google_project_id
        and settings.google_redirect_uri
    ):
        raise HTTPException(500, "Google OAuth not configured; set GOOGLE_* env vars")
    return {
        "web": {
            "client_id": settings.google_client_id,
            "project_id": settings.google_project_id,
            "auth_uri": AUTH_URI,
            "token_uri": TOKEN_URI,
            "client_secret": settings.google_client_secret,
            "redirect_uris": [str(settings.google_redirect_uri)],
        }
    }


class TokenStore:
    def __init__(self, root: str):
        self.root = pathlib.Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, profile_id: str, email: str) -> pathlib.Path:
        safe = email.replace("@", "_at_")
        return self.root / f"{profile_id}__{safe}.json"

    def save(self, profile_id: str, email: str, creds: Credentials):
        data = {
            "token": getattr(creds, "token", None),
            "refresh_token": getattr(creds, "refresh_token", None),
            "token_uri": getattr(creds, "token_uri", TOKEN_URI),
            "client_id": getattr(creds, "client_id", settings.google_client_id),
            "client_secret": getattr(creds, "client_secret", settings.google_client_secret),
            "scopes": list(getattr(creds, "scopes", settings.google_scopes) or []),
            "expiry": getattr(creds, "expiry", None).timestamp() if getattr(creds, "expiry", None) else None,
        }
        self.path(profile_id, email).write_text(json.dumps(data))

    def load(self, profile_id: str, email: str) -> Optional[Credentials]:
        p = self.path(profile_id, email)
        if not p.exists():
            return None
        data = json.loads(p.read_text())
        try:
            creds = Credentials(
                token=data.get("token"),
                refresh_token=data.get("refresh_token"),
                token_uri=data.get("token_uri", TOKEN_URI),
                client_id=data.get("client_id", settings.google_client_id),
                client_secret=data.get("client_secret", settings.google_client_secret),
                scopes=data.get("scopes", settings.google_scopes),
            )
        except Exception as e:  # pragma: no cover
            logger.error("Failed to construct Credentials: %s", e)
            return None
        return creds


store = TokenStore(settings.token_store_dir)
state_signer = URLSafeSerializer(settings.secret_key, salt="gmail-state")


class GmailService:
    @staticmethod
    def auth_url(profile_id: str) -> str:
        flow = Flow.from_client_config(_client_config(), scopes=settings.google_scopes)
        flow.redirect_uri = str(settings.google_redirect_uri)
        auth_url, state = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="consent",
            state=state_signer.dumps({"profile_id": profile_id, "ts": int(time.time())}),
        )
        logger.info("Generated Gmail auth URL for profile_id=%s", profile_id)
        return auth_url

    @staticmethod
    def exchange_code(code: str, state: str) -> dict:
        try:
            payload = state_signer.loads(state, max_age=600)
        except Exception:
            raise HTTPException(400, "Invalid or expired state")

        profile_id = payload["profile_id"]
        flow = Flow.from_client_config(_client_config(), scopes=settings.google_scopes)
        flow.redirect_uri = str(settings.google_redirect_uri)
        flow.fetch_token(code=code)
        creds: Credentials = flow.credentials

        svc = build("gmail", "v1", credentials=creds)
        me = svc.users().getProfile(userId="me").execute()
        email = me["emailAddress"]

        store.save(profile_id, email, creds)
        logger.info("Stored Gmail credentials for profile_id=%s email=%s", profile_id, email)
        return {"profile_id": profile_id, "email": email, "scopes": list(creds.scopes or [])}

    @staticmethod
    def client_for(profile_id: str, email: str):
        creds = store.load(profile_id, email)
        if not creds:
            raise HTTPException(404, "No credentials stored for this profile/email")
        if hasattr(creds, "valid") and not creds.valid and getattr(creds, "refresh_token", None):
            try:
                creds.refresh(Request())
                store.save(profile_id, email, creds)
            except Exception as e:  # pragma: no cover
                logger.error("Failed to refresh token: %s", e)
                raise HTTPException(401, "Failed to refresh token")
        return build("gmail", "v1", credentials=creds)

    @staticmethod
    def list_messages(profile_id: str, email: str, q: str = "newer_than:7d", max_results: int = 10):
        svc = GmailService.client_for(profile_id, email)
        try:
            resp = (
                svc.users()
                .messages()
                .list(userId="me", q=q, maxResults=max_results)
                .execute()
            )
        except Exception as e:
            # Provide a clearer hint if scope is insufficient for 'q'
            msg = str(e)
            if "Metadata scope does not support 'q'" in msg:
                from fastapi import HTTPException

                raise HTTPException(
                    400,
                    "Your token lacks gmail.readonly. Reconnect Gmail (prompt=consent) or revoke access and relink.",
                )
            raise
        return resp.get("messages", [])

    @staticmethod
    def watch_mailbox(profile_id: str, email: str, label_ids=None):
        label_ids = label_ids or ["INBOX"]
        if not settings.gcp_pubsub_topic:
            raise HTTPException(500, "GCP_PUBSUB_TOPIC not configured")
        svc = GmailService.client_for(profile_id, email)
        body = {
            "topicName": settings.gcp_pubsub_topic,
            "labelIds": label_ids,
            "labelFilterBehavior": "INCLUDE",
        }
        return svc.users().watch(userId="me", body=body).execute()

    @staticmethod
    def get_profile(profile_id: str, email: str) -> dict:
        svc = GmailService.client_for(profile_id, email)
        return svc.users().getProfile(userId="me").execute()

    @staticmethod
    def list_accounts(profile_id: str) -> list[str]:
        emails: list[str] = []
        prefix = f"{profile_id}__"
        for p in store.root.glob(f"{prefix}*.json"):
            name = p.name
            try:
                masked = name[len(prefix):].rsplit(".json", 1)[0]
                emails.append(masked.replace("_at_", "@"))
            except Exception:
                continue
        return sorted(emails)

    @staticmethod
    def list_all_accounts() -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for p in store.root.glob("*.json"):
            name = p.name
            try:
                prefix, rest = name.split("__", 1)
                email = rest.rsplit(".json", 1)[0].replace("_at_", "@")
                out.append((prefix, email))
            except Exception:
                continue
        return sorted(out)

    @staticmethod
    def token_scopes(profile_id: str, email: str) -> list[str]:
        creds = store.load(profile_id, email)
        return list(getattr(creds, "scopes", []) or []) if creds else []

    @staticmethod
    def get_message(
        profile_id: str,
        email: str,
        message_id: str,
        fmt: str = "metadata",
        metadata_headers: list[str] | None = None,
    ) -> dict:
        svc = GmailService.client_for(profile_id, email)
        kwargs: dict = {"userId": "me", "id": message_id, "format": fmt}
        if fmt == "metadata":
            kwargs["metadataHeaders"] = metadata_headers or ["From", "To", "Subject", "Date"]
        return svc.users().messages().get(**kwargs).execute()

    @staticmethod
    def extract_plaintext(message: dict) -> str | None:
        """Extract best-effort text/plain from a Gmail message (format=full)."""
        import base64

        def _decode(b64: str) -> str:
            try:
                return base64.urlsafe_b64decode(b64 + "==").decode("utf-8", errors="replace")
            except Exception:
                return ""

        payload = message.get("payload", {})

        # Direct body
        body = payload.get("body", {})
        data = body.get("data")
        if data:
            return _decode(data)

        # Walk parts for text/plain
        stack = payload.get("parts", []) or []
        while stack:
            part = stack.pop()
            mime = part.get("mimeType", "")
            if mime == "text/plain":
                pdata = part.get("body", {}).get("data")
                if pdata:
                    return _decode(pdata)
            # nested multipart
            if part.get("parts"):
                stack.extend(part["parts"])
        return None

    @staticmethod
    def extract_html(message: dict) -> str | None:
        """Extract best-effort text/html from a Gmail message (format=full)."""
        import base64

        def _decode(b64: str) -> str:
            try:
                return base64.urlsafe_b64decode(b64 + "==").decode("utf-8", errors="replace")
            except Exception:
                return ""

        payload = message.get("payload", {})

        # Direct body
        body = payload.get("body", {})
        data = body.get("data")
        if data and str(payload.get("mimeType", "")).startswith("text/html"):
            return _decode(data)

        # Walk parts, prefer text/html over text/plain
        html_candidate = None
        stack = payload.get("parts", []) or []
        while stack:
            part = stack.pop()
            mime = str(part.get("mimeType", ""))
            if mime.startswith("text/html"):
                pdata = part.get("body", {}).get("data")
                if pdata:
                    return _decode(pdata)
            if part.get("parts"):
                stack.extend(part["parts"])
        return html_candidate

    @staticmethod
    def parse_headers(message: dict) -> dict:
        headers = {}
        for h in (message.get("payload", {}).get("headers", []) or []):
            name = h.get("name")
            value = h.get("value")
            if name:
                headers[name] = value
        return headers

    @staticmethod
    def list_attachments_from_message(message: dict) -> list[dict]:
        """Return list of attachments from a message (format=full)."""
        out: list[dict] = []
        payload = message.get("payload", {})
        stack = [payload]
        while stack:
            part = stack.pop()
            body = part.get("body", {}) or {}
            filename = part.get("filename") or ""
            if body.get("attachmentId") and filename:
                out.append(
                    {
                        "filename": filename,
                        "mimeType": part.get("mimeType"),
                        "size": body.get("size"),
                        "attachmentId": body.get("attachmentId"),
                        "partId": part.get("partId"),
                    }
                )
            for child in (part.get("parts") or []):
                stack.append(child)
        return out

    @staticmethod
    def download_attachment(profile_id: str, email: str, message_id: str, attachment_id: str) -> bytes:
        svc = GmailService.client_for(profile_id, email)
        att = (
            svc.users()
            .messages()
            .attachments()
            .get(userId="me", messageId=message_id, id=attachment_id)
            .execute()
        )
        import base64

        data = att.get("data")
        return base64.urlsafe_b64decode(data + "==") if data else b""

    @staticmethod
    def search_messages_enriched(
        profile_id: str,
        email: str,
        q: str,
        max_results: int = 10,
    ) -> list[dict]:
        ids = GmailService.list_messages(profile_id, email, q=q, max_results=max_results)
        results: list[dict] = []
        for item in ids:
            mid = item.get("id")
            if not mid:
                continue
            msg = GmailService.get_message(profile_id, email, mid, fmt="metadata")
            headers = GmailService.parse_headers(msg)
            results.append(
                {
                    "id": mid,
                    "threadId": msg.get("threadId"),
                    "from": headers.get("From"),
                    "to": headers.get("To"),
                    "subject": headers.get("Subject"),
                    "date": headers.get("Date"),
                    "snippet": msg.get("snippet"),
                }
            )
        return results
