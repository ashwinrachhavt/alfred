from __future__ import annotations

import datetime as dt
import logging
import smtplib
from email.message import EmailMessage
from typing import Any, Iterable

from sqlmodel import Session, select

from alfred.core.database import get_session
from alfred.core.settings import settings
from alfred.schemas.outreach import OutreachContact, OutreachMessage
from alfred.services.company_outreach import ContactDiscoveryService

logger = logging.getLogger(__name__)


def _row_to_dict(contact: OutreachContact) -> dict[str, Any]:
    return {
        "name": contact.name,
        "title": contact.title,
        "email": contact.email,
        "confidence": contact.confidence,
        "source": contact.source,
    }


class OutreachService:
    """Handles contact discovery caching and outbound outreach message logging/sending."""

    def __init__(self, *, session: Session | None = None) -> None:
        self.session = session

    # -------- contacts --------
    def list_contacts(
        self,
        company: str,
        *,
        limit: int = 20,
        role_filter: str | None = None,
        refresh: bool = False,
    ) -> list[dict[str, Any]]:
        if not refresh:
            cached = self._get_cached_contacts(company, role_filter=role_filter, limit=limit)
            if cached:
                return cached

        contacts = ContactDiscoveryService(session=self.session).discover(company, limit=limit)
        if role_filter:
            role_l = role_filter.lower()
            contacts = [c for c in contacts if role_l in (c.get("title") or "").lower()]
        return contacts[:limit]

    def _get_cached_contacts(
        self, company: str, *, role_filter: str | None, limit: int
    ) -> list[dict[str, Any]]:
        ttl_hours = max(0, int(getattr(settings, "outreach_cache_ttl_hours", 0)))
        cutoff = (dt.datetime.utcnow() - dt.timedelta(hours=ttl_hours)) if ttl_hours > 0 else None

        sess_ctx = self.session or next(get_session())
        with sess_ctx as db:
            stmt = select(OutreachContact).where(OutreachContact.company == company)
            if cutoff is not None:
                stmt = stmt.where(OutreachContact.created_at >= cutoff)
            stmt = stmt.order_by(OutreachContact.confidence.desc()).limit(limit * 2)
            rows: Iterable[OutreachContact] = db.exec(stmt).all()
            if not rows:
                return []
            items = [_row_to_dict(row) for row in rows]
            if role_filter:
                role_l = role_filter.lower()
                items = [c for c in items if role_l in (c.get("title") or "").lower()]
            return items[:limit]

    # -------- sending --------
    def send_email(
        self,
        *,
        company: str,
        contact_email: str,
        subject: str,
        body: str,
        contact_name: str = "",
        contact_title: str = "",
        dry_run: bool = False,
    ) -> OutreachMessage:
        message = OutreachMessage(
            company=company,
            contact_email=contact_email,
            contact_name=contact_name,
            contact_title=contact_title,
            subject=subject,
            body=body,
            provider="smtp",
            status="queued",
            meta={"dry_run": dry_run},
        )

        sess_ctx = self.session or next(get_session())
        with sess_ctx as db:
            db.add(message)
            db.flush()

            should_send = (
                settings.outreach_send_enabled
                and not dry_run
                and settings.smtp_host
                and settings.smtp_from_email
            )
            if should_send:
                try:
                    self._send_via_smtp(
                        to_email=contact_email,
                        subject=subject,
                        body=body,
                        reply_to=settings.smtp_from_email,
                    )
                    message.status = "sent"
                    message.sent_at = dt.datetime.utcnow()
                except Exception as exc:  # pragma: no cover - network path
                    logger.warning("SMTP send failed: %s", exc)
                    message.status = "failed"
                    message.error_message = str(exc)
            else:
                message.status = "skipped"
                message.error_message = message.error_message or "sending disabled or dry_run"

            db.add(message)
            db.commit()
            db.refresh(message)
            return message

    def _send_via_smtp(self, *, to_email: str, subject: str, body: str, reply_to: str) -> None:
        msg = EmailMessage()
        msg["From"] = reply_to
        msg["To"] = to_email
        msg["Subject"] = subject
        msg["Reply-To"] = reply_to
        msg.set_content(body)

        host = settings.smtp_host
        port = settings.smtp_port
        if not host:
            raise RuntimeError("SMTP_HOST not configured")

        server = smtplib.SMTP(host, port, timeout=20)
        try:
            if settings.smtp_use_tls:
                server.starttls()
            if settings.smtp_username and settings.smtp_password:
                server.login(settings.smtp_username, settings.smtp_password)
            server.send_message(msg)
        finally:
            try:
                server.quit()
            except Exception:  # pragma: no cover - best effort cleanup
                pass
