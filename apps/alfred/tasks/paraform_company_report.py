from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

from celery import shared_task

from alfred.core.dependencies import (
    get_company_research_service,
    get_datastore_service,
    get_interview_questions_service,
)
from alfred.services.llm_service import LLMService

logger = logging.getLogger(__name__)


def _stable_id(*, company: str, role: str | None, location: str | None) -> str:
    raw = f"{(company or '').strip()}|{(role or '').strip()}|{(location or '').strip()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _make_interview_strategy(
    *,
    llm: LLMService,
    company: str,
    role: str | None,
    executive_summary: str,
    top_questions: list[str],
) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "You are an interview coach and researcher. "
                "Produce concise, high-signal guidance with actionable bullets."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Company: {company}\n"
                f"Role: {role or '(unspecified)'}\n\n"
                f"Executive summary:\n{(executive_summary or '').strip()}\n\n"
                "Observed interview questions:\n"
                + "\n".join([f"- {q}" for q in top_questions[:18]])
                + "\n\n"
                "Write:\n"
                "1) 5 bullets: what they likely value\n"
                "2) 5 bullets: how to prepare (projects, stories, drills)\n"
                "3) 5 bullets: smart questions to ask interviewers\n"
                "Keep it tight and specific to the company; avoid fluff."
            ),
        },
    ]
    return llm.chat(messages, temperature=0.2).strip()


@shared_task(name="alfred.tasks.paraform_company_report.generate")
def paraform_company_report_task(
    *,
    company: str,
    role: str | None = None,
    location: str | None = None,
    category: str | None = None,
    seniority: str | None = None,
    remote_available: str | None = None,
    refresh: bool = False,
    collection: str = "paraform_company_reports",
) -> dict[str, Any]:
    """Generate and store a Paraform company report (research + questions + strategy).

    This task is designed to run in Celery workers so work is parallelized across companies.
    It persists results into Postgres via DataStoreService (JSON document store).
    """
    company_clean = (company or "").strip()
    if not company_clean:
        raise ValueError("company must be non-empty")

    research_service = get_company_research_service()
    questions_service = get_interview_questions_service()
    store = get_datastore_service().with_collection(collection)
    llm = LLMService()

    logger.info("Generating Paraform report for %s (refresh=%s)", company_clean, refresh)

    company_research: dict[str, Any]
    try:
        company_research = research_service.generate_report(company_clean, refresh=refresh)
    except Exception as exc:
        company_research = {"company": company_clean, "error": str(exc)}

    interview_questions: dict[str, Any] | None
    try:
        interview_questions = questions_service.generate_report(
            company_clean, role=role
        ).model_dump(mode="json")
    except Exception as exc:
        interview_questions = {"company": company_clean, "role": role, "error": str(exc)}

    executive_summary = ""
    if isinstance(company_research, dict):
        report = company_research.get("report")
        if isinstance(report, dict):
            executive_summary = str(report.get("executive_summary") or "")

    top_qs: list[str] = []
    if isinstance(interview_questions, dict):
        for q in interview_questions.get("questions") or []:
            if isinstance(q, dict) and q.get("question"):
                top_qs.append(str(q["question"]))

    interview_strategy = ""
    try:
        interview_strategy = _make_interview_strategy(
            llm=llm,
            company=company_clean,
            role=role,
            executive_summary=executive_summary,
            top_questions=top_qs,
        )
    except Exception as exc:
        interview_strategy = f"(Interview strategy generation failed: {exc})"

    payload: dict[str, Any] = {
        "_id": _stable_id(company=company_clean, role=role, location=location),
        "company": company_clean,
        "role": role,
        "location": location,
        "category": category,
        "seniority": seniority,
        "remote_available": remote_available,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "company_research": company_research,
        "interview_questions": interview_questions,
        "interview_strategy": interview_strategy,
    }

    store.update_one({"_id": payload["_id"]}, {"$set": payload}, upsert=True)
    return payload


__all__ = ["paraform_company_report_task"]
