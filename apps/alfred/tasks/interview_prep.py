from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from celery import shared_task

from alfred.core.dependencies import get_interview_prep_service
from alfred.core.settings import settings
from alfred.schemas.interview_prep import InterviewPrepUpdate, InterviewReminders
from alfred.services.interview_calendar import InterviewCalendarService
from alfred.services.interview_prep import (
    InterviewChecklistService,
    InterviewPrepDocGenerator,
    InterviewPrepRenderer,
    InterviewQuizGenerator,
)

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.utcnow().replace(tzinfo=timezone.utc)


def _send_slack(text: str) -> None:
    channel = (settings.interview_notifications_slack_channel or "").strip()
    if not channel:
        return
    try:
        from alfred.services.slack import SlackService

        SlackService().send_message(channel=channel, text=text)
    except Exception:
        # Best-effort notifications only.
        return


@shared_task(name="alfred.tasks.interview_prep.generate")
def generate_interview_prep_task(*, interview_id: str, force: bool = False) -> dict[str, Any]:
    """Generate prep doc + quiz for an interview record (idempotent-ish).

    This task is intended to be triggered after detection or on-demand.
    """
    svc = get_interview_prep_service()
    record = svc.get(interview_id)
    if record is None:
        return {
            "ok": False,
            "error": "Interview prep record not found",
            "interview_id": interview_id,
        }

    if (not force) and record.get("generated_at"):
        return {"ok": True, "interview_id": interview_id, "skipped": True}

    company = str(record.get("company") or "").strip()
    role = str(record.get("role") or "").strip()
    interview_type = (
        record.get("interview_type") if isinstance(record.get("interview_type"), str) else None
    )
    interview_date = (
        record.get("interview_date") if isinstance(record.get("interview_date"), datetime) else None
    )

    logger.info("Generating interview prep for %s (%s)", company, role)
    prep_doc = InterviewPrepDocGenerator().generate_prep_doc(
        company=company,
        role=role,
        interview_type=interview_type,
        interview_date=interview_date,
    )
    quiz = InterviewQuizGenerator().generate_quiz(company=company, role=role, prep_doc=prep_doc)
    md = InterviewPrepRenderer().render(company=company, role=role, doc=prep_doc)

    svc.update(
        interview_id,
        InterviewPrepUpdate(
            prep_doc=prep_doc,
            prep_markdown=md,
            prep_markdown_generated_at=_utcnow(),
            quiz=quiz,
            generated_at=_utcnow(),
        ),
    )

    if (
        settings.enable_interview_calendar_events
        and interview_date
        and not record.get("calendar_event")
    ):
        try:
            meeting_link = None
            source = record.get("source")
            if isinstance(source, dict):
                detected = source.get("detected")
                if isinstance(detected, dict):
                    links = detected.get("meeting_links") or []
                    if isinstance(links, list) and links:
                        meeting_link = str(links[0])

            cal = InterviewCalendarService().create_interview_event(
                company=company,
                role=role,
                start=interview_date,
                meeting_link=meeting_link,
            )
            if cal is not None:
                svc.update(interview_id, InterviewPrepUpdate(calendar_event=cal))
        except Exception:
            pass

    _send_slack(f"Prep ready: {company} — {role} (id={interview_id})")
    return {"ok": True, "interview_id": interview_id}


@shared_task(name="alfred.tasks.interview_prep.send_reminders")
def send_interview_reminders_task(*, horizon_days: int = 14) -> dict[str, Any]:
    """Send interview reminders for upcoming interviews.

    Runs best-effort. Uses Slack notifications when configured.
    """
    if not settings.enable_interview_reminders:
        return {"ok": False, "reason": "ENABLE_INTERVIEW_REMINDERS is not enabled"}

    svc = get_interview_prep_service()
    now = _utcnow()
    horizon = now + timedelta(days=max(1, min(int(horizon_days), 60)))

    docs = svc.find_by_interview_date(
        start=now - timedelta(days=1),
        end=horizon,
        projection={
            "company": 1,
            "role": 1,
            "interview_date": 1,
            "interview_type": 1,
            "prep_doc": 1,
            "source": 1,
            "reminders": 1,
        },
    )

    sent = {"start_prep": 0, "review": 0, "checklist": 0}
    examined = 0
    for doc in docs:
        examined += 1
        interview_id = str(doc.get("_id"))
        interview_date = doc.get("interview_date")
        if not isinstance(interview_date, datetime):
            continue
        if interview_date.tzinfo is None:
            interview_date = interview_date.replace(tzinfo=timezone.utc)

        company = str(doc.get("company") or "").strip()
        role = str(doc.get("role") or "").strip()
        interview_type = (
            doc.get("interview_type") if isinstance(doc.get("interview_type"), str) else None
        )
        prep_doc = doc.get("prep_doc") if isinstance(doc.get("prep_doc"), dict) else None
        source = doc.get("source") if isinstance(doc.get("source"), dict) else None
        existing = doc.get("reminders") or {}
        reminders = InterviewReminders.model_validate(existing)

        due_start_prep = now >= (interview_date - timedelta(days=3))
        due_review_and_checklist = now >= (interview_date - timedelta(days=1))
        due_final_checklist = now >= (interview_date - timedelta(hours=1))

        changed = False
        if due_start_prep and reminders.start_prep_sent_at is None:
            _send_slack(f"Interview in ~3 days: start prep — {company} ({role})")
            reminders.start_prep_sent_at = now
            sent["start_prep"] += 1
            changed = True

        if due_review_and_checklist and reminders.checklist_sent_at is None:
            try:
                checklist = InterviewChecklistService().generate(
                    company=company,
                    role=role,
                    interview_type=interview_type,
                    interview_date=interview_date,
                    prep_doc=prep_doc,
                    source=source,
                )
                svc.update(
                    interview_id,
                    InterviewPrepUpdate(
                        checklist=checklist,
                        checklist_generated_at=now,
                    ),
                )
            except Exception:
                pass

            _send_slack(f"Interview in ~1 day: review + checklist — {company} ({role})")
            reminders.review_sent_at = now
            reminders.checklist_sent_at = now
            sent["review"] += 1
            sent["checklist"] += 1
            changed = True

        if due_final_checklist and reminders.final_checklist_sent_at is None:
            _send_slack(f"Interview in ~1 hour: checklist — {company} ({role})")
            reminders.final_checklist_sent_at = now
            changed = True

        if changed:
            try:
                svc.update(interview_id, InterviewPrepUpdate(reminders=reminders))
            except Exception:
                continue

    return {"ok": True, "examined": examined, "sent": sent}
