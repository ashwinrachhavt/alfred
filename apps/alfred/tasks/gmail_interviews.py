from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from celery import shared_task

from alfred.connectors.google_gmail_connector import GoogleGmailConnector
from alfred.core.celery_client import get_celery_client
from alfred.core.dependencies import get_interview_prep_service
from alfred.core.settings import settings
from alfred.schemas.interview_prep import InterviewPrepCreate
from alfred.services.gmail import GmailService
from alfred.services.google_oauth import load_credentials, persist_credentials
from alfred.services.interview_detection import InterviewDetectionService

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.utcnow().replace(tzinfo=timezone.utc)


def _get_gmail_connector() -> GoogleGmailConnector | None:
    creds = load_credentials(namespace="gmail")
    if creds is None:
        return None
    return GoogleGmailConnector(
        creds,
        user_id=None,
        on_credentials_refreshed=lambda c: persist_credentials(None, c, namespace="gmail"),
    )


@shared_task(name="alfred.tasks.gmail.poll_interviews")
def poll_gmail_for_interviews_task(*, days_back: int = 7, max_results: int = 25) -> dict[str, Any]:
    """Poll Gmail for interview-like messages and create interview prep records.

    This is a pragmatic alternative to push notifications. It is best-effort and
    dedupes via a unique sparse index on `source.gmail_message_id`.
    """
    if not settings.enable_gmail or not settings.enable_gmail_interview_poll:
        return {"ok": False, "reason": "Gmail polling disabled"}

    connector = _get_gmail_connector()
    if connector is None:
        return {"ok": False, "reason": "No Gmail credentials configured"}

    days = max(1, min(int(days_back), 30))
    limit = max(1, min(int(max_results), 100))

    query = 'newer_than:%dd (interview OR "phone screen" OR onsite OR screening)' % days

    async def _run() -> dict[str, Any]:
        messages, err = await connector.get_messages_list(max_results=limit, query=query)
        if err:
            return {"ok": False, "error": err}

        svc = get_interview_prep_service()
        created = 0
        examined = 0
        scheduled = 0
        detector = InterviewDetectionService()
        celery = get_celery_client()

        for msg in messages:
            msg_id = msg.get("id")
            if not isinstance(msg_id, str) or not msg_id:
                continue
            examined += 1

            message, detail_err = await connector.get_message_details(msg_id)
            if detail_err:
                continue

            headers = GmailService.parse_headers(message)
            subject = headers.get("Subject") or headers.get("subject") or ""
            body = GmailService.extract_plaintext(message) or ""
            if not detector.is_interview_candidate(email_text=body, subject=subject):
                continue

            det = detector.detect(
                email_text=body, subject=subject, company_hint=None, role_hint=None
            )
            company = det.company or "Unknown"
            role = det.role or "Unknown"

            try:
                interview_id = svc.create(
                    InterviewPrepCreate(
                        company=company,
                        role=role,
                        interview_date=det.interview_date,
                        interview_type=det.interview_type,
                        source={
                            "gmail_message_id": msg_id,
                            "subject": subject,
                            "detected": {"meeting_links": det.meeting_links or []},
                        },
                    )
                )
                created += 1

                celery.send_task(
                    "alfred.tasks.interview_prep.generate",
                    kwargs={"interview_id": interview_id},
                )
                scheduled += 1
            except Exception:
                # Duplicate key (already processed) or validation errors.
                continue

        return {"ok": True, "examined": examined, "created": created, "scheduled": scheduled}

    return asyncio.run(_run())


__all__ = ["poll_gmail_for_interviews_task"]
