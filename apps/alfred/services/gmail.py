from __future__ import annotations

import base64
from typing import Any, Dict, List, Optional


def _b64url_decode(data: Optional[str]) -> Optional[bytes]:
    if not data:
        return None
    # Gmail API uses URL-safe base64 without padding
    s = data.replace("-", "+").replace("_", "/")
    pad = len(s) % 4
    if pad:
        s += "=" * (4 - pad)
    try:
        return base64.b64decode(s)
    except Exception:
        return None


class GmailService:
    """Lightweight utilities for parsing Gmail message payloads.

    This module intentionally omits network calls. It focuses on extracting
    text/html bodies, headers, and attachment metadata from a Gmail Message dict
    as returned by the Gmail REST API.
    """

    @staticmethod
    def parse_headers(message: Dict[str, Any]) -> Dict[str, str]:
        headers = {}
        try:
            for h in (message.get("payload", {}) or {}).get("headers", []) or []:
                name = h.get("name")
                val = h.get("value")
                if name and val is not None:
                    headers[name] = val
        except Exception:
            pass
        return headers

    @staticmethod
    def _find_parts(message: Dict[str, Any]) -> List[Dict[str, Any]]:
        payload = message.get("payload", {}) or {}
        parts = payload.get("parts") or []
        return parts if isinstance(parts, list) else []

    @staticmethod
    def _body_text_for_mime(message: Dict[str, Any], mime: str) -> Optional[str]:
        payload = message.get("payload", {}) or {}
        # Direct body if matches
        if payload.get("mimeType") == mime:
            data = ((payload.get("body") or {}).get("data"))
            decoded = _b64url_decode(data)
            if decoded is not None:
                try:
                    return decoded.decode("utf-8", errors="replace")
                except Exception:
                    return None
        # Search parts
        for p in GmailService._find_parts(message):
            if p.get("mimeType") == mime:
                data = ((p.get("body") or {}).get("data"))
                decoded = _b64url_decode(data)
                if decoded is not None:
                    try:
                        return decoded.decode("utf-8", errors="replace")
                    except Exception:
                        return None
        return None

    @staticmethod
    def extract_plaintext(message: Dict[str, Any]) -> Optional[str]:
        txt = GmailService._body_text_for_mime(message, "text/plain")
        if txt:
            return txt
        # Fallback: attempt to strip HTML if only html exists
        html = GmailService._body_text_for_mime(message, "text/html")
        if html:
            # Minimal strip: remove tags crudely
            import re

            return re.sub(r"<[^>]+>", "", html)
        # Last resort: snippet
        return message.get("snippet")

    @staticmethod
    def extract_html(message: Dict[str, Any]) -> Optional[str]:
        html = GmailService._body_text_for_mime(message, "text/html")
        if html:
            return html
        # If only text/plain exists, wrap it
        txt = GmailService._body_text_for_mime(message, "text/plain")
        if txt:
            return f"<pre>{txt}</pre>"
        return None

    @staticmethod
    def list_attachments_from_message(message: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Return attachment metadata from message parts.

        Each item: {filename, mimeType, attachmentId, size}
        """
        attachments: List[Dict[str, Any]] = []
        for p in GmailService._find_parts(message):
            body = p.get("body") or {}
            filename = p.get("filename") or ""
            mime = p.get("mimeType") or ""
            att_id = body.get("attachmentId")
            size = body.get("size")
            # Heuristic: consider as attachment if an attachmentId exists or a filename is present
            if att_id or (filename and not mime.startswith("text/")):
                attachments.append(
                    {
                        "filename": filename,
                        "mimeType": mime,
                        "attachmentId": att_id,
                        "size": size,
                    }
                )
        return attachments

