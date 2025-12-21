from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from alfred.connectors.google_gmail_connector import GoogleGmailConnector
from alfred.core.celery_client import get_celery_client
from alfred.core.dependencies import get_interview_prep_service, get_job_application_service
from alfred.schemas.interview_prep import (
    InterviewChecklist,
    InterviewFeedback,
    InterviewPrepCreate,
    InterviewPrepUpdate,
    InterviewQuiz,
    PrepDoc,
    QuizAttempt,
)
from alfred.schemas.job_applications import JobApplicationStatus, JobApplicationUpdate
from alfred.services.gmail import GmailService
from alfred.services.google_oauth import load_credentials, persist_credentials
from alfred.services.interview_checklist import InterviewChecklistService
from alfred.services.interview_detection import InterviewDetectionService
from alfred.services.interview_prep import InterviewPrepService
from alfred.services.interview_prep_generator import InterviewPrepDocGenerator
from alfred.services.interview_prep_renderer import InterviewPrepRenderer
from alfred.services.interview_quiz_generator import InterviewQuizGenerator

router = APIRouter(prefix="/api/interviews", tags=["interviews"])


def _utcnow() -> datetime:
    return datetime.utcnow().replace(tzinfo=timezone.utc)


def get_prep_doc_generator() -> InterviewPrepDocGenerator:
    return InterviewPrepDocGenerator()


def get_quiz_generator() -> InterviewQuizGenerator:
    return InterviewQuizGenerator()


def get_gmail_connector_maybe() -> GoogleGmailConnector | None:
    creds = load_credentials(namespace="gmail")
    if creds is None:
        return None
    return GoogleGmailConnector(
        creds,
        user_id=None,
        on_credentials_refreshed=lambda c: persist_credentials(None, c, namespace="gmail"),
    )


class InterviewDetectRequest(BaseModel):
    """Detect (or directly supply) interview details and create a prep record."""

    job_application_id: str | None = None
    company: str | None = None
    role: str | None = None
    interview_date: datetime | None = None
    interview_type: str | None = None

    subject: str | None = None
    email_text: str | None = None
    gmail_message_id: str | None = None


class InterviewDetectResponse(BaseModel):
    interview_prep_id: str
    detected: dict[str, Any]
    task_id: str | None = None


@router.post("/detect", response_model=InterviewDetectResponse)
async def detect_interview(
    payload: InterviewDetectRequest,
    svc: InterviewPrepService = Depends(get_interview_prep_service),
    gmail: GoogleGmailConnector | None = Depends(get_gmail_connector_maybe),
    background: bool = False,
    job_apps=Depends(get_job_application_service),
) -> InterviewDetectResponse:
    # Minimal v1: accept explicit company/role, optionally enrich from email_text.
    company = (payload.company or "").strip() or None
    role = (payload.role or "").strip() or None

    subject = payload.subject
    email_text = payload.email_text
    if (not email_text) and payload.gmail_message_id:
        if gmail is None:
            raise HTTPException(
                404, "No Google credentials found; authorize via /api/gmail/auth_url"
            )
        message, err = await gmail.get_message_details(payload.gmail_message_id)
        if err:
            raise HTTPException(status_code=400, detail=err)
        headers = GmailService.parse_headers(message)
        subject = subject or headers.get("Subject") or headers.get("subject")
        email_text = GmailService.extract_plaintext(message) or ""

    detected: dict[str, Any] = {}
    if email_text:
        det = InterviewDetectionService().detect(
            email_text=email_text,
            subject=subject,
            company_hint=company,
            role_hint=role,
        )
        detected = {
            "company": det.company,
            "role": det.role,
            "interview_type": det.interview_type,
            "interview_date": det.interview_date,
            "meeting_links": det.meeting_links or [],
        }
        company = company or det.company
        role = role or det.role

    if not company or not role:
        raise HTTPException(
            status_code=422,
            detail="company and role are required (or provide email_text/gmail_message_id with extractable details)",
        )

    job_app_id: str | None = None
    raw_job_app_id = (payload.job_application_id or "").strip() or None
    if raw_job_app_id and ObjectId.is_valid(raw_job_app_id):
        job_app_id = raw_job_app_id

    source: dict[str, Any] = {}
    raw_job_app_id = (payload.job_application_id or "").strip() or None
    job_app_id: str | None = None
    if raw_job_app_id and ObjectId.is_valid(raw_job_app_id):
        job_app_id = raw_job_app_id
    if raw_job_app_id and not job_app_id:
        source["job_application_id_raw"] = raw_job_app_id
    if payload.gmail_message_id:
        source["gmail_message_id"] = payload.gmail_message_id
    if subject:
        source["subject"] = subject
    if email_text:
        source["email_text_excerpt"] = email_text[:800]
    if detected:
        source["detected"] = detected

    created_id = svc.create(
        InterviewPrepCreate(
            job_application_id=job_app_id,
            company=company,
            role=role,
            interview_date=payload.interview_date or detected.get("interview_date"),
            interview_type=payload.interview_type or detected.get("interview_type"),
            source=source or None,
        )
    )

    if job_app_id:
        try:
            job_apps.update(
                job_app_id, JobApplicationUpdate(status=JobApplicationStatus.interview_scheduled)
            )
        except Exception:
            pass

    task_id: str | None = None
    if background:
        try:
            celery = get_celery_client()
            async_result = celery.send_task(
                "alfred.tasks.interview_prep.generate",
                kwargs={"interview_id": created_id},
            )
            task_id = async_result.id
        except Exception:
            task_id = None

    return InterviewDetectResponse(interview_prep_id=created_id, detected=detected, task_id=task_id)


class GeneratePrepRequest(BaseModel):
    candidate_background: str | None = Field(
        default=None,
        description="Optional background/projects context to improve STAR stories and role analysis.",
    )


@router.post("/{interview_id}/prep", response_model=PrepDoc)
def generate_prep_doc(
    interview_id: str,
    payload: GeneratePrepRequest,
    svc: InterviewPrepService = Depends(get_interview_prep_service),
    gen: InterviewPrepDocGenerator = Depends(get_prep_doc_generator),
) -> PrepDoc:
    record = svc.get(interview_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Interview prep record not found")

    company = str(record.get("company") or "").strip()
    role = str(record.get("role") or "").strip()
    interview_type = (
        record.get("interview_type") if isinstance(record.get("interview_type"), str) else None
    )
    interview_date = (
        record.get("interview_date") if isinstance(record.get("interview_date"), datetime) else None
    )

    doc = gen.generate_prep_doc(
        company=company,
        role=role,
        interview_type=interview_type,
        interview_date=interview_date,
        candidate_background=payload.candidate_background,
    )

    md = InterviewPrepRenderer().render(company=company, role=role, doc=doc)
    svc.update(
        interview_id,
        InterviewPrepUpdate(
            prep_doc=doc,
            prep_markdown=md,
            prep_markdown_generated_at=_utcnow(),
            generated_at=_utcnow(),
        ),
    )
    return doc


@router.get("/{interview_id}/prep", response_model=PrepDoc)
def get_prep_doc(
    interview_id: str,
    svc: InterviewPrepService = Depends(get_interview_prep_service),
) -> PrepDoc:
    record = svc.get(interview_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Interview prep record not found")
    prep_doc = record.get("prep_doc") or {}
    try:
        return PrepDoc.model_validate(prep_doc)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Invalid prep_doc schema: {exc}") from exc


@router.get("/{interview_id}/prep/markdown")
def get_prep_markdown(
    interview_id: str,
    svc: InterviewPrepService = Depends(get_interview_prep_service),
) -> dict[str, Any]:
    record = svc.get(interview_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Interview prep record not found")

    md = record.get("prep_markdown")
    if isinstance(md, str) and md.strip():
        return {"markdown": md}

    prep_doc = PrepDoc.model_validate(record.get("prep_doc") or {})
    company = str(record.get("company") or "").strip()
    role = str(record.get("role") or "").strip()
    rendered = InterviewPrepRenderer().render(company=company, role=role, doc=prep_doc)
    svc.update(
        interview_id,
        InterviewPrepUpdate(prep_markdown=rendered, prep_markdown_generated_at=_utcnow()),
    )
    return {"markdown": rendered}


@router.get("/{interview_id}/checklist", response_model=InterviewChecklist)
def get_checklist(
    interview_id: str,
    refresh: bool = False,
    svc: InterviewPrepService = Depends(get_interview_prep_service),
) -> InterviewChecklist:
    record = svc.get(interview_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Interview prep record not found")

    existing = record.get("checklist")
    if (not refresh) and existing:
        try:
            return InterviewChecklist.model_validate(existing)
        except Exception:
            pass

    checklist = InterviewChecklistService().generate(
        company=str(record.get("company") or ""),
        role=str(record.get("role") or ""),
        interview_type=str(record.get("interview_type") or "") or None,
        interview_date=record.get("interview_date")
        if isinstance(record.get("interview_date"), datetime)
        else None,
        prep_doc=record.get("prep_doc") if isinstance(record.get("prep_doc"), dict) else None,
        source=record.get("source") if isinstance(record.get("source"), dict) else None,
    )
    svc.update(
        interview_id,
        InterviewPrepUpdate(checklist=checklist, checklist_generated_at=_utcnow()),
    )
    return checklist


class GenerateQuizRequest(BaseModel):
    num_questions: int = Field(default=12, ge=5, le=25)


@router.post("/{interview_id}/quiz", response_model=InterviewQuiz)
def generate_quiz(
    interview_id: str,
    payload: GenerateQuizRequest,
    svc: InterviewPrepService = Depends(get_interview_prep_service),
    gen: InterviewQuizGenerator = Depends(get_quiz_generator),
) -> InterviewQuiz:
    record = svc.get(interview_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Interview prep record not found")

    company = str(record.get("company") or "").strip()
    role = str(record.get("role") or "").strip()
    prep_doc = PrepDoc.model_validate(record.get("prep_doc") or {})

    quiz = gen.generate_quiz(
        company=company,
        role=role,
        prep_doc=prep_doc,
        num_questions=payload.num_questions,
    )
    svc.update(interview_id, InterviewPrepUpdate(quiz=quiz))
    return quiz


def _normalize_answer(text: str) -> str:
    import re

    t = (text or "").lower().strip()
    t = re.sub(r"[\s]+", " ", t)
    t = re.sub(r"[^\w\s]+", "", t)
    return t.strip()


class QuizAttemptRequest(BaseModel):
    """Submit answers for a generated quiz attempt.

    `answers` is a mapping of question index -> user's answer.
    """

    answers: dict[int, str] = Field(default_factory=dict)


@router.post("/{interview_id}/quiz/attempt")
def submit_quiz_attempt(
    interview_id: str,
    payload: QuizAttemptRequest,
    svc: InterviewPrepService = Depends(get_interview_prep_service),
) -> dict[str, Any]:
    record = svc.get(interview_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Interview prep record not found")

    quiz = InterviewQuiz.model_validate(record.get("quiz") or {})
    if not quiz.questions:
        raise HTTPException(status_code=422, detail="No quiz questions found for this interview")

    total_gradable = 0
    correct = 0
    graded: dict[int, bool | None] = {}
    for idx, q in enumerate(quiz.questions):
        user_ans = payload.answers.get(idx)
        if user_ans is None:
            continue
        if not q.answer:
            graded[idx] = None
            continue
        total_gradable += 1
        ok = _normalize_answer(user_ans) == _normalize_answer(q.answer)
        graded[idx] = ok
        if ok:
            correct += 1

    score = (correct / total_gradable) if total_gradable > 0 else 0.0
    attempt = QuizAttempt(
        taken_at=_utcnow(),
        score=score,
        answers={"by_index": payload.answers, "graded": graded},
    )
    quiz.attempts.append(attempt)
    quiz.score = score

    svc.update(interview_id, InterviewPrepUpdate(quiz=quiz))
    return {"ok": True, "score": score, "gradable": total_gradable, "correct": correct}


class FeedbackRequest(BaseModel):
    performance_rating: Optional[int] = Field(default=None, ge=1, le=10)
    confidence_rating: Optional[int] = Field(default=None, ge=1, le=10)
    helpful_materials: list[str] | None = None
    actual_questions: list[str] | None = None
    improvements: list[str] | None = None
    notes: str | None = None


@router.patch("/{interview_id}/feedback")
def post_feedback(
    interview_id: str,
    payload: FeedbackRequest,
    svc: InterviewPrepService = Depends(get_interview_prep_service),
) -> dict[str, Any]:
    if (
        payload.performance_rating is None
        and payload.confidence_rating is None
        and payload.helpful_materials is None
        and payload.actual_questions is None
        and payload.improvements is None
        and payload.notes is None
    ):
        raise HTTPException(status_code=422, detail="At least one feedback field must be provided")

    feedback = None
    if (
        payload.helpful_materials is not None
        or payload.actual_questions is not None
        or payload.improvements is not None
        or payload.notes is not None
    ):
        feedback = InterviewFeedback(
            helpful_materials=payload.helpful_materials or [],
            actual_questions=payload.actual_questions or [],
            improvements=payload.improvements or [],
            notes=payload.notes,
        )

    ok = svc.update(
        interview_id,
        InterviewPrepUpdate(
            performance_rating=payload.performance_rating,
            confidence_rating=payload.confidence_rating,
            feedback=feedback,
        ),
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Interview prep record not found")
    return {"ok": True}


@router.get("")
def list_interviews(
    company: str | None = None,
    limit: int = 20,
    svc: InterviewPrepService = Depends(get_interview_prep_service),
) -> dict[str, Any]:
    lim = max(1, min(int(limit), 100))
    filt: dict[str, Any] = {}
    if company and company.strip():
        filt["company"] = company.strip()

    docs = (
        svc._collection.find(  # type: ignore[attr-defined]
            filt,
            projection={
                "company": 1,
                "role": 1,
                "interview_date": 1,
                "interview_type": 1,
                "generated_at": 1,
                "performance_rating": 1,
                "confidence_rating": 1,
            },
        )
        .sort("interview_date", 1)
        .limit(lim)
    )
    items = []
    for d in docs:
        d["id"] = str(d.pop("_id"))
        items.append(d)
    return {"count": len(items), "items": items}


@router.get("/stats")
def interview_stats(
    limit: int = 500,
    svc: InterviewPrepService = Depends(get_interview_prep_service),
) -> dict[str, Any]:
    lim = max(1, min(int(limit), 2000))
    docs = svc._collection.find(  # type: ignore[attr-defined]
        {},
        projection={"company": 1, "performance_rating": 1, "confidence_rating": 1},
    ).limit(lim)

    total = 0
    by_company: dict[str, dict[str, Any]] = {}
    perf_sum = perf_n = 0
    conf_sum = conf_n = 0

    for d in docs:
        total += 1
        company = str(d.get("company") or "Unknown").strip() or "Unknown"
        bucket = by_company.setdefault(
            company, {"count": 0, "perf_sum": 0, "perf_n": 0, "conf_sum": 0, "conf_n": 0}
        )
        bucket["count"] += 1

        perf = d.get("performance_rating")
        if isinstance(perf, int):
            perf_sum += perf
            perf_n += 1
            bucket["perf_sum"] += perf
            bucket["perf_n"] += 1

        conf = d.get("confidence_rating")
        if isinstance(conf, int):
            conf_sum += conf
            conf_n += 1
            bucket["conf_sum"] += conf
            bucket["conf_n"] += 1

    companies = []
    for name, agg in by_company.items():
        companies.append(
            {
                "company": name,
                "count": agg["count"],
                "avg_performance": (agg["perf_sum"] / agg["perf_n"]) if agg["perf_n"] else None,
                "avg_confidence": (agg["conf_sum"] / agg["conf_n"]) if agg["conf_n"] else None,
            }
        )
    companies.sort(key=lambda x: x["count"], reverse=True)

    return {
        "total": total,
        "avg_performance": (perf_sum / perf_n) if perf_n else None,
        "avg_confidence": (conf_sum / conf_n) if conf_n else None,
        "companies": companies[:25],
    }


__all__ = ["router", "get_gmail_connector_maybe", "get_prep_doc_generator", "get_quiz_generator"]
