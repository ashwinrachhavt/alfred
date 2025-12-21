from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from alfred.core.dependencies import (
    get_company_research_service,
    get_doc_storage_service,
    get_llm_service,
)
from alfred.prompts import load_prompt
from alfred.schemas.interview_prep import PrepDoc

SYSTEM_PROMPT = load_prompt("interview_prep", "system.md")
PREP_DOC_PROMPT = load_prompt("interview_prep", "prep_doc.md")


def _safe_json(obj: Any, *, max_chars: int) -> str:
    try:
        text = json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    except Exception:
        text = str(obj)
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n…"


def _safe_text(text: str | None, *, max_chars: int) -> str:
    s = (text or "").strip()
    if len(s) <= max_chars:
        return s
    return s[:max_chars] + "\n…"


@dataclass
class InterviewPrepDocGenerator:
    """Generate an interview prep document (PrepDoc) from available context."""

    llm: Any = None
    company_research_service: Any = None
    doc_storage: Any = None

    def __post_init__(self) -> None:
        if self.llm is None:
            self.llm = get_llm_service()
        if self.company_research_service is None:
            self.company_research_service = get_company_research_service()
        if self.doc_storage is None:
            self.doc_storage = get_doc_storage_service()

    def generate_prep_doc(
        self,
        *,
        company: str,
        role: str,
        interview_type: Optional[str] = None,
        interview_date: Optional[datetime] = None,
        candidate_background: str | None = None,
        notes_query: str | None = None,
        notes_k: int = 6,
    ) -> PrepDoc:
        """Generate a PrepDoc using company research + notes as context."""
        company = (company or "").strip()
        role = (role or "").strip()
        if not company:
            raise ValueError("company is required")
        if not role:
            raise ValueError("role is required")

        cached_research = None
        try:
            cached_research = self.company_research_service.get_cached_report(company)
        except Exception:
            cached_research = None

        notes_blob = ""
        try:
            q = (notes_query or company).strip()
            if q:
                notes = self.doc_storage.list_notes(q=q, skip=0, limit=max(1, min(notes_k, 20)))
                items = notes.get("items") if isinstance(notes, dict) else None
                if isinstance(items, list):
                    texts = [str(it.get("text", "")).strip() for it in items[:notes_k]]
                    notes_blob = "\n\n".join([t for t in texts if t])
        except Exception:
            notes_blob = ""

        doc_summaries = ""
        try:
            qd = f"{company} {role}".strip()
            docs = self.doc_storage.list_documents(q=qd, skip=0, limit=6)
            items = docs.get("items") if isinstance(docs, dict) else None
            if isinstance(items, list) and items:
                lines = []
                for it in items[:6]:
                    title = str(it.get("title") or "").strip() or "(untitled)"
                    src = str(it.get("source_url") or "").strip()
                    summ = str(it.get("summary") or "").strip()
                    line = f"- {title}"
                    if src:
                        line += f" ({src})"
                    if summ:
                        line += f": {summ}"
                    lines.append(line)
                doc_summaries = "\n".join(lines)
        except Exception:
            doc_summaries = ""

        if not candidate_background:
            try:
                seeds = ["CodeRabbit", "Zoox", "Oscillar"]
                project_notes = []
                for seed in seeds:
                    res = self.doc_storage.list_notes(q=seed, skip=0, limit=3)
                    items = res.get("items") if isinstance(res, dict) else None
                    if isinstance(items, list):
                        project_notes.extend([str(it.get("text", "")).strip() for it in items[:2]])
                project_notes = [t for t in project_notes if t]
                if project_notes:
                    candidate_background = "\n\n".join(project_notes[:6])
            except Exception:
                candidate_background = candidate_background

        user_prompt = PREP_DOC_PROMPT.format(
            company=company,
            role=role,
            interview_type=(interview_type or "").strip() or "unknown",
            interview_date=interview_date.isoformat() if interview_date else "unknown",
            company_research=_safe_json(cached_research or {}, max_chars=18_000),
            notes=_safe_text(
                (
                    notes_blob
                    + ("\n\n=== Relevant documents ===\n" + doc_summaries if doc_summaries else "")
                ).strip(),
                max_chars=12_000,
            )
            or "(none)",
            candidate_background=_safe_text(candidate_background, max_chars=10_000) or "(none)",
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            return self.llm.structured(messages=messages, schema=PrepDoc)
        except Exception:
            raw = self.llm.chat(messages=messages)
            try:
                return PrepDoc.model_validate_json(raw)
            except Exception as exc:
                raise ValueError("Failed to parse PrepDoc JSON from model output") from exc


__all__ = ["InterviewPrepDocGenerator"]
