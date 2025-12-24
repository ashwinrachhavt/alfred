from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol

from alfred.core.settings import settings
from alfred.prompts import load_prompt
from alfred.schemas.interview_prep import (
    InterviewChecklist,
    InterviewPrepCreate,
    InterviewPrepRecord,
    InterviewPrepUpdate,
    InterviewQuiz,
    PrepDoc,
)
from alfred.services.datastore import DataStoreService


class _LLM(Protocol):
    def structured(self, *, messages: list[dict[str, str]], schema: type[PrepDoc]):  # noqa: ANN201
        ...

    def chat(self, *, messages: list[dict[str, str]]):  # noqa: ANN201
        ...


_JSON_BLOCK_RE = re.compile(r"\{.*\}", flags=re.DOTALL)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_json_object(text: str) -> str:
    """Extract a JSON object from an LLM response (best-effort).

    The LLM is instructed to return only JSON, but in practice it may wrap it in
    code fences or include leading/trailing commentary. This helper extracts the
    first object-shaped substring.
    """
    raw = (text or "").strip()
    if not raw:
        raise ValueError("Empty LLM response")

    # Strip common Markdown code fences.
    if raw.startswith("```"):
        raw = re.sub(r"^```(json)?", "", raw, flags=re.IGNORECASE).strip()
        raw = re.sub(r"```$", "", raw).strip()

    m = _JSON_BLOCK_RE.search(raw)
    if not m:
        raise ValueError("Could not locate JSON object in LLM response")
    return m.group(0)


def _parse_prep_doc(text: str) -> PrepDoc:
    blob = _coerce_json_object(text)
    try:
        return PrepDoc.model_validate_json(blob)
    except Exception:
        # Some models emit trailing commas or other minor issues; try a json
        # round-trip through Python to normalize.
        obj = json.loads(blob)
        return PrepDoc.model_validate(obj)


@dataclass
class InterviewPrepDocGenerator:
    """Generate structured interview preparation documents via an LLM."""

    llm: _LLM | Any | None = None
    company_research_service: Any | None = None
    doc_storage: Any | None = None
    max_notes: int = 6

    def __post_init__(self) -> None:
        if self.llm is None:
            from alfred.core.dependencies import get_llm_service

            self.llm = get_llm_service()
        if self.company_research_service is None:
            from alfred.core.dependencies import get_company_research_service

            self.company_research_service = get_company_research_service()
        if self.doc_storage is None:
            from alfred.core.dependencies import get_doc_storage_service

            self.doc_storage = get_doc_storage_service()

    def generate_prep_doc(
        self,
        *,
        company: str,
        role: str,
        interview_type: str | None = None,
        interview_date: datetime | None = None,
        candidate_background: str | None = None,
    ) -> PrepDoc:
        company = (company or "").strip()
        role = (role or "").strip()
        if not company:
            raise ValueError("company must be non-empty")
        if not role:
            raise ValueError("role must be non-empty")

        interview_type = (interview_type or "").strip() or "N/A"
        interview_date_str = (
            interview_date.astimezone(timezone.utc).isoformat()
            if isinstance(interview_date, datetime)
            else "N/A"
        )

        company_research: Mapping[str, Any] | None = None
        try:
            company_research = self.company_research_service.get_cached_report(company)
        except Exception:
            company_research = None

        notes_text = ""
        try:
            if self.doc_storage is not None:
                res = self.doc_storage.list_notes(
                    q=company, skip=0, limit=max(1, min(int(self.max_notes), 20))
                )
                items = res.get("items") if isinstance(res, dict) else None
                if isinstance(items, list):
                    chunks = []
                    for it in items[: self.max_notes]:
                        if isinstance(it, dict) and isinstance(it.get("text"), str):
                            chunks.append(it["text"])
                    notes_text = "\n".join(chunks).strip()
        except Exception:
            notes_text = ""

        sys = load_prompt("interview_prep", "system.md")
        user = load_prompt("interview_prep", "prep_doc.md").format(
            company=company,
            role=role,
            interview_type=interview_type,
            interview_date=interview_date_str,
            company_research=json.dumps(company_research or {}, ensure_ascii=False, indent=2),
            notes=notes_text or "",
            candidate_background=(candidate_background or "").strip(),
        )
        messages = [
            {"role": "system", "content": sys},
            {"role": "user", "content": user},
        ]

        try:
            return self.llm.structured(messages=messages, schema=PrepDoc)
        except Exception:
            text = self.llm.chat(messages=messages)
            return _parse_prep_doc(text)


@dataclass
class InterviewQuizGenerator:
    """Generate a lightweight practice quiz derived from a prep document."""

    llm: Any | None = None

    def __post_init__(self) -> None:
        if self.llm is None:
            from alfred.core.dependencies import get_llm_service

            self.llm = get_llm_service()

    def generate_quiz(
        self,
        *,
        company: str,
        role: str,
        prep_doc: PrepDoc,
        num_questions: int = 12,
    ) -> InterviewQuiz:
        company = (company or "").strip()
        role = (role or "").strip()
        if not company or not role:
            return InterviewQuiz()

        sys = load_prompt("interview_prep", "system.md")
        user = load_prompt("interview_prep", "quiz.md").format(
            company=company,
            role=role,
            num_questions=max(1, min(int(num_questions), 50)),
            prep_doc=prep_doc.model_dump_json(indent=2),
        )
        messages = [
            {"role": "system", "content": sys},
            {"role": "user", "content": user},
        ]

        # Quiz schema is small enough to use chat JSON parsing everywhere.
        raw = self.llm.chat(messages=messages)
        try:
            obj = json.loads(_coerce_json_object(raw))
        except Exception:
            return InterviewQuiz()
        try:
            return InterviewQuiz.model_validate(obj)
        except Exception:
            return InterviewQuiz()


class InterviewPrepRenderer:
    """Render a `PrepDoc` into readable Markdown."""

    def render(self, *, company: str, role: str, doc: PrepDoc) -> str:
        company = (company or "").strip() or "Company"
        role = (role or "").strip() or "Role"

        lines: list[str] = [f"# Interview Prep — {company} ({role})", ""]
        if doc.company_overview.strip():
            lines.extend(["## Company Overview", doc.company_overview.strip(), ""])
        if doc.role_analysis.strip():
            lines.extend(["## Role Analysis", doc.role_analysis.strip(), ""])

        if doc.star_stories:
            lines.append("## STAR Stories")
            for idx, s in enumerate(doc.star_stories, start=1):
                title = (s.title or f"Story {idx}").strip()
                lines.extend(
                    [
                        f"### {title}",
                        f"- **Situation:** {s.situation}",
                        f"- **Task:** {s.task}",
                        f"- **Action:** {s.action}",
                        f"- **Result:** {s.result}",
                    ]
                )
                if s.skills:
                    lines.append(f"- **Skills:** {', '.join(s.skills)}")
                lines.append("")

        if doc.likely_questions:
            lines.append("## Likely Questions")
            for q in doc.likely_questions:
                lines.append(f"- **Q:** {q.question}")
                if q.suggested_answer:
                    lines.append(f"  - **A:** {q.suggested_answer}")
                if q.focus_areas:
                    lines.append(f"  - **Focus:** {', '.join(q.focus_areas)}")
            lines.append("")

        if doc.technical_topics:
            lines.append("## Technical Topics")
            for t in sorted(doc.technical_topics, key=lambda x: (x.priority, x.topic.lower())):
                base = f"- **P{t.priority}** {t.topic}"
                if t.notes:
                    base += f" — {t.notes}"
                lines.append(base)
                for r in t.resources[:4]:
                    if r:
                        lines.append(f"  - {r}")
            lines.append("")

        return "\n".join(lines).strip()


class InterviewChecklistService:
    """Generate a short day-of checklist for an interview."""

    def generate(
        self,
        *,
        company: str,
        role: str,
        interview_type: str | None = None,
        interview_date: datetime | None = None,
        prep_doc: Mapping[str, Any] | PrepDoc | None = None,
        source: Mapping[str, Any] | None = None,
    ) -> InterviewChecklist:
        _ = prep_doc, source
        company = (company or "").strip() or "Company"
        role = (role or "").strip() or "Role"

        when = (
            interview_date.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            if isinstance(interview_date, datetime)
            else "N/A"
        )
        interview_type = (interview_type or "").strip() or "interview"

        markdown = "\n".join(
            [
                f"# Interview Checklist — {company} ({role})",
                "",
                f"**Type:** {interview_type}",
                f"**When:** {when}",
                "",
                "## Setup",
                "- Confirm time zone and meeting link",
                "- Charge laptop + test audio/video",
                "- Have water + notes ready",
                "",
                "## Content",
                "- Review 3–5 STAR stories",
                "- Refresh top technical topics",
                "- Prepare 3 questions to ask",
                "",
                "## Mindset",
                "- Slow down; clarify the problem before solving",
                "- Narrate tradeoffs and assumptions",
                "- End with crisp recap and next steps",
            ]
        ).strip()

        return InterviewChecklist(
            markdown=markdown,
            timeline=[
                "T-30m: Setup and environment check",
                "T-10m: Review STAR bullets + key topics",
                "T+0: Join early, confirm format",
                "T+5m: Clarify goals and expectations",
                "T+final: Ask questions + confirm next steps",
            ],
            talking_points=["Relevant projects", "Impact metrics", "Tradeoffs and decisions"],
            questions_to_ask=[
                "What does success look like in the first 90 days?",
                "What are the biggest technical challenges on the team right now?",
                "How do you evaluate engineering quality and impact?",
            ],
            setup=["Meeting link", "IDE/editor ready", "Whiteboard tool ready"],
            mindset=["Be curious", "Be structured", "Communicate clearly"],
        )


@dataclass
class InterviewPrepService:
    """CRUD + index management for interview prep records.

    Defaults to Alfred's Postgres-backed `DataStoreService`. If a Mongo-like
    `database` is provided, it will be used for index creation only (best-effort)
    to preserve backward compatibility.
    """

    database: Any | None = None
    collection_name: str = settings.interview_prep_collection

    def __post_init__(self) -> None:
        self._store = DataStoreService(default_collection=self.collection_name)

    def ensure_indexes(self) -> None:
        """Create legacy Mongo indexes when a compatible collection is available.

        This is a no-op for the Postgres-backed datastore and is best-effort by
        design: failures should not prevent the application from starting.
        """
        if self.database is None:
            return
        try:
            coll = self.database.get_collection(self.collection_name)
        except Exception:
            return

        try:
            coll.create_index([("job_application_id", 1)], name="job_app_id")
            coll.create_index([("company", 1)], name="company")
            coll.create_index([("interview_date", 1)], name="interview_date")
            coll.create_index([("generated_at", -1)], name="generated_at_desc")
        except Exception:
            return

    def create(self, payload: InterviewPrepCreate) -> str:
        now = _utcnow().isoformat()
        base = payload.model_dump(mode="json")
        doc = {
            **base,
            "prep_doc": PrepDoc().model_dump(mode="json"),
            "quiz": InterviewQuiz().model_dump(mode="json"),
            "created_at": now,
            "updated_at": now,
        }
        InterviewPrepRecord.model_validate(doc)
        return self._store.insert_one(doc)

    def get(self, interview_id: str) -> dict[str, Any] | None:
        doc = self._store.find_one({"_id": interview_id})
        if not doc:
            return None
        InterviewPrepRecord.model_validate(doc)
        out = dict(doc)
        out["id"] = str(out.pop("_id"))
        return out

    def update(self, interview_id: str, patch: InterviewPrepUpdate) -> bool:
        update = patch.model_dump(exclude_none=True, mode="json")
        update["updated_at"] = _utcnow().isoformat()
        res = self._store.update_one({"_id": interview_id}, {"$set": update})
        return bool(res.get("matched_count", 0))


__all__ = [
    "InterviewChecklistService",
    "InterviewPrepDocGenerator",
    "InterviewPrepRenderer",
    "InterviewPrepService",
    "InterviewQuizGenerator",
]
