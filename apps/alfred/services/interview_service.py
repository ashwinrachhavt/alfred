"""Interview feature service implementation.

This is the canonical module for the "interview" feature and consolidates
detection, question collection, prep generation/storage, and the unified
interview agent workflow.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Iterable, Literal, Mapping, Protocol, TypedDict

from dateutil import parser as date_parser
from dateutil import tz as date_tz
from fastapi.concurrency import run_in_threadpool
from langgraph.graph import END, START, StateGraph

from alfred.connectors.firecrawl_connector import FirecrawlClient, FirecrawlResponse
from alfred.connectors.web_connector import SearchHit, SearchResponse, WebConnector
from alfred.core.settings import LLMProvider, settings
from alfred.core.utils import clamp_int
from alfred.core.utils import utcnow as _utcnow
from alfred.prompts import load_prompt
from alfred.schemas.interview_prep import (
    InterviewChecklist,
    InterviewPrepCreate,
    InterviewPrepRecord,
    InterviewPrepUpdate,
    InterviewQuiz,
    PrepDoc,
)
from alfred.schemas.interview_questions import (
    InterviewQuestionsReport,
    QuestionItem,
    QuestionSource,
)
from alfred.schemas.panel_interview import (
    PanelConfig,
    PanelSession,
    PanelSessionCreate,
    PanelTurnRequest,
    PanelTurnResponse,
)
from alfred.schemas.unified_interview import (
    UnifiedInterviewOperation,
    UnifiedInterviewRequest,
    UnifiedInterviewResponse,
    UnifiedQuestion,
)
from alfred.services.datastore import DataStoreService
from alfred.services.utils import extract_questions_heuristic, normalize_question


@dataclass(frozen=True, slots=True)
class InterviewDetection:
    """Result of parsing an email for interview details.

    The detector is intentionally heuristic-based and conservative. When fields
    cannot be extracted confidently, they are left as `None` so downstream code
    can apply defaults.
    """

    company: str | None = None
    role: str | None = None
    interview_date: datetime | None = None
    interview_type: str | None = None
    meeting_links: list[str] | None = None


class InterviewDetectionService:
    """Detect interview-related information from email subject/body."""

    _KEYWORDS = (
        "interview",
        "phone screen",
        "screening",
        "onsite",
        "on-site",
        "technical screen",
        "coding interview",
        "schedule",
        "scheduled",
        "availability",
    )

    _TYPE_KEYWORDS: tuple[tuple[str, str], ...] = (
        ("phone screen", "phone_screen"),
        ("technical screen", "technical_screen"),
        ("coding interview", "coding_interview"),
        ("onsite", "onsite"),
        ("on-site", "onsite"),
        ("screening", "screening"),
    )

    _MEETING_LINK_HOST_HINTS = (
        "zoom.us",
        "meet.google.com",
        "teams.microsoft.com",
        "webex.com",
        "calendly.com",
        "hirevue.com",
        "goodtime.io",
    )

    _TZINFOS: dict[str, object] = {
        # Common US timezone abbreviations seen in scheduling emails.
        "PT": date_tz.gettz("America/Los_Angeles"),
        "PST": date_tz.gettz("America/Los_Angeles"),
        "PDT": date_tz.gettz("America/Los_Angeles"),
        "MT": date_tz.gettz("America/Denver"),
        "MST": date_tz.gettz("America/Denver"),
        "MDT": date_tz.gettz("America/Denver"),
        "CT": date_tz.gettz("America/Chicago"),
        "CST": date_tz.gettz("America/Chicago"),
        "CDT": date_tz.gettz("America/Chicago"),
        "ET": date_tz.gettz("America/New_York"),
        "EST": date_tz.gettz("America/New_York"),
        "EDT": date_tz.gettz("America/New_York"),
        "UTC": date_tz.UTC,
        "GMT": date_tz.UTC,
    }

    def is_interview_candidate(self, *, email_text: str, subject: str) -> bool:
        """Return True if the email likely relates to an interview."""
        text = self._normalize_text(" ".join([subject, email_text]))
        return any(keyword in text for keyword in self._KEYWORDS)

    def detect(
        self,
        *,
        email_text: str,
        subject: str,
        company_hint: str | None,
        role_hint: str | None,
    ) -> InterviewDetection:
        """Extract interview metadata from email content.

        This method never raises on unparseable input; it returns a best-effort
        `InterviewDetection` with missing fields left as `None`.
        """
        normalized_subject = self._normalize_text(subject)
        normalized_body = self._normalize_text(email_text)

        company = self._clean_hint(company_hint) or self._extract_company_from_subject(subject)
        role = self._clean_hint(role_hint) or self._extract_role_from_subject(subject)
        interview_type = self._infer_interview_type(normalized_subject, normalized_body)
        interview_date = self._extract_datetime(subject, email_text)
        meeting_links = self._extract_meeting_links(subject, email_text)

        return InterviewDetection(
            company=company,
            role=role,
            interview_date=interview_date,
            interview_type=interview_type,
            meeting_links=meeting_links or None,
        )

    def _infer_interview_type(self, subject: str, body: str) -> str | None:
        text = f"{subject} {body}"
        for needle, label in self._TYPE_KEYWORDS:
            if needle in text:
                return label
        return None

    def _extract_company_from_subject(self, subject: str) -> str | None:
        subj = subject.strip()
        if not subj:
            return None

        # Examples:
        # - "Interview at Acme — Software Engineer"
        # - "Acme | Phone Screen for Backend Engineer"
        patterns = (
            r"\b(?:interview|phone screen|screening|onsite|on-site)\s+(?:at|with)\s+(?P<company>[^|–—:-]+)",
            r"^(?P<company>[^|–—:-]+)\s*(?:[|–—:-]\s*)\b(?:interview|phone screen|screening|onsite|on-site)\b",
        )
        for pat in patterns:
            match = re.search(pat, subj, flags=re.IGNORECASE)
            if match:
                candidate = match.group("company").strip()
                return self._clean_extracted_value(candidate)
        return None

    def _extract_role_from_subject(self, subject: str) -> str | None:
        subj = subject.strip()
        if not subj:
            return None

        patterns = (
            r"\bfor\s+(?P<role>[^|–—:-]+)",
            r"\brole\s*[:\-]\s*(?P<role>[^|–—]+)",
        )
        for pat in patterns:
            match = re.search(pat, subj, flags=re.IGNORECASE)
            if match:
                candidate = match.group("role").strip()
                return self._clean_extracted_value(candidate)
        return None

    def _extract_datetime(self, subject: str, body: str) -> datetime | None:
        candidates = [subject, body]
        for snippet in self._candidate_datetime_snippets(candidates):
            parsed = self._try_parse_datetime(snippet)
            if parsed is not None:
                return parsed
        return None

    def _candidate_datetime_snippets(self, texts: Iterable[str]) -> Iterable[str]:
        # Prefer short windows around common scheduling words to avoid random parses.
        anchor = re.compile(
            r"\b(?:on|at|scheduled for|schedule for|rescheduled to|rescheduled for)\b.{0,80}",
            flags=re.IGNORECASE | re.DOTALL,
        )
        for text in texts:
            if not text:
                continue
            for match in anchor.finditer(text):
                snippet = match.group(0).strip()
                # Keep the snippet short and avoid URLs/extra tokens confusing the parser.
                snippet = snippet.splitlines()[0]
                snippet = snippet.split("http", 1)[0].strip()
                if snippet:
                    yield snippet

    def _try_parse_datetime(self, text: str) -> datetime | None:
        try:
            dt = date_parser.parse(text, fuzzy=True, tzinfos=self._TZINFOS)
        except Exception:
            return None

        # Avoid returning clearly incorrect parses (e.g., year 1900 from missing year).
        if dt.year < 2000:
            return None
        return dt

    def _extract_meeting_links(self, subject: str, body: str) -> list[str]:
        urls = self._extract_urls(f"{subject}\n{body}")
        meeting_links: list[str] = []
        for url in urls:
            if any(hint in url for hint in self._MEETING_LINK_HOST_HINTS):
                meeting_links.append(url)
        return self._unique_preserve_order(meeting_links)

    def _extract_urls(self, text: str) -> list[str]:
        # Conservative URL extractor; avoids trailing punctuation.
        candidates = re.findall(r"https?://[^\s<>()]+", text, flags=re.IGNORECASE)
        cleaned: list[str] = []
        for url in candidates:
            cleaned.append(url.rstrip(").,;:!?\"'"))
        return self._unique_preserve_order(cleaned)

    def _unique_preserve_order(self, items: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []
        for item in items:
            if item in seen:
                continue
            seen.add(item)
            result.append(item)
        return result

    def _clean_hint(self, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    def _clean_extracted_value(self, value: str) -> str | None:
        cleaned = re.sub(r"\s+", " ", value).strip()
        if not cleaned:
            return None
        # Avoid common mail prefixes masquerading as company/role values.
        if cleaned.lower().startswith(("re:", "fw:", "fwd:")):
            return None
        return cleaned

    def _normalize_text(self, value: str) -> str:
        return re.sub(r"\s+", " ", value or "").strip().lower()


def _categorize(question: str) -> list[str]:
    q = (question or "").lower()
    categories: list[str] = []

    behavioral_kw = (
        "conflict",
        "coworker",
        "team",
        "leadership",
        "failure",
        "challenge",
        "feedback",
        "strength",
        "weakness",
        "disagree",
        "stakeholder",
    )
    system_kw = (
        "system design",
        "design ",
        "architecture",
        "distributed",
        "cap theorem",
        "cache",
        "load balancer",
        "throughput",
        "latency",
        "consistency",
        "partition",
        "database",
        "feature store",
        "uber",
        "scal",
    )
    coding_kw = (
        "algorithm",
        "data structure",
        "complexity",
        "big o",
        "leetcode",
        "array",
        "string",
        "graph",
        "tree",
        "dynamic programming",
        "dp",
        "hash",
        "sort",
        "binary search",
        "two pointers",
        "stack",
        "queue",
    )
    ml_kw = (
        "model",
        "training",
        "overfitting",
        "embedding",
        "transformer",
        "llm",
        "prompt",
    )

    if any(k in q for k in behavioral_kw):
        categories.append("behavioral")
    if any(k in q for k in system_kw):
        categories.append("system_design")
    if any(k in q for k in coding_kw):
        categories.append("coding")
    if any(k in q for k in ml_kw):
        categories.append("ml")

    return categories or ["general"]


def _unique_sources(urls: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        key = (u or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(u)
    return out


@dataclass
class InterviewQuestionsService:
    """Collect and normalize interview questions from public sources."""

    primary_search: Any | None = None
    fallback_search: Any | None = None
    firecrawl: Any | None = None
    search_results: int = 8
    firecrawl_search_results: int = 6

    def __post_init__(self) -> None:
        if self.primary_search is None:
            self.primary_search = WebConnector(mode="auto", searx_k=self.search_results)
        if self.fallback_search is None:
            self.fallback_search = self.primary_search
        if self.firecrawl is None:
            self.firecrawl = FirecrawlClient(
                base_url=settings.firecrawl_base_url,
                timeout=settings.firecrawl_timeout,
            )

    def generate_report(
        self,
        company: str,
        *,
        role: str | None = None,
        max_sources: int = 12,
        max_questions: int = 60,
        use_firecrawl_search: bool = True,
    ) -> InterviewQuestionsReport:
        company = (company or "").strip()
        role_clean = (role or "").strip() or None
        if not company:
            raise ValueError("company must be non-empty")

        max_sources = max(1, int(max_sources))
        max_questions = max(1, int(max_questions))

        base = f"{company} {role_clean}".strip()
        queries = [
            f"{base} coding interview questions".strip(),
            f"{base} interview questions".strip(),
        ]

        warnings: list[str] = []
        sources: list[QuestionSource] = []
        urls: list[str] = []

        def _search(conn: Any, query: str) -> SearchResponse | None:
            try:
                return conn.search(query)
            except Exception as exc:
                warnings.append(f"Search failed for query '{query}': {exc}")
                return None

        for q in queries:
            res = _search(self.primary_search, q)
            if res is None or not getattr(res, "hits", None):
                res = _search(self.fallback_search, q)
            if res is None:
                continue
            hits = list(res.hits or [])[: max(1, self.search_results)]
            for hit in hits:
                if not isinstance(hit, SearchHit) or not hit.url:
                    continue
                urls.append(hit.url)
                sources.append(
                    QuestionSource(
                        url=hit.url,
                        title=hit.title,
                        snippet=hit.snippet,
                        provider=str(getattr(res, "provider", None) or hit.source),
                    )
                )

        if use_firecrawl_search and self.firecrawl is not None:
            try:
                fire = self.firecrawl.search(
                    f"{base} interview questions".strip(),
                    max_results=max(1, int(self.firecrawl_search_results)),
                )
            except Exception as exc:  # pragma: no cover - network/provider errors
                fire = FirecrawlResponse(success=False, error=str(exc))
            if fire.success and isinstance(fire.data, list):
                for item in fire.data[: max(1, self.firecrawl_search_results)]:
                    if not isinstance(item, dict):
                        continue
                    url = item.get("url")
                    if not isinstance(url, str) or not url.strip():
                        continue
                    urls.append(url)
                    content = item.get("content")
                    extracted = extract_questions_heuristic(
                        content if isinstance(content, str) else None, max_questions=8
                    )
                    sources.append(
                        QuestionSource(
                            url=url,
                            title=item.get("title") if isinstance(item.get("title"), str) else None,
                            snippet=content if isinstance(content, str) else None,
                            provider="firecrawl",
                            questions=extracted,
                        )
                    )

        urls = _unique_sources(urls)[:max_sources]

        def _scrape(url: str) -> tuple[str | None, str | None]:
            try:
                resp = self.firecrawl.scrape(url, render_js=False)
            except Exception as exc:  # pragma: no cover - network/provider errors
                return None, str(exc)
            if not getattr(resp, "success", False):
                err = getattr(resp, "error", None)
                return None, err if isinstance(err, str) else str(err)
            return getattr(resp, "markdown", None), None

        by_url: dict[str, QuestionSource] = {s.url: s for s in sources if s.url}
        for url in urls:
            markdown, error = _scrape(url)
            qs = extract_questions_heuristic(markdown, max_questions=16)
            existing = by_url.get(url)
            if existing is None:
                sources.append(
                    QuestionSource(url=url, provider="firecrawl", questions=qs, error=error)
                )
            else:
                existing.error = existing.error or error
                existing.questions = _unique_sources(existing.questions + qs)  # type: ignore[arg-type]

        # Aggregate questions across sources.
        items: dict[str, QuestionItem] = {}
        for src in sources:
            for q in src.questions:
                norm = normalize_question(q)
                key = norm.lower()
                entry = items.get(key)
                if entry is None:
                    entry = QuestionItem(
                        question=norm,
                        categories=_categorize(norm),
                        occurrences=0,
                        sources=[],
                    )
                    items[key] = entry
                entry.occurrences += 1
                if src.url and src.url not in entry.sources:
                    entry.sources.append(src.url)

        question_list = sorted(
            items.values(),
            key=lambda x: (-x.occurrences, x.question.lower()),
        )[:max_questions]

        return InterviewQuestionsReport(
            company=company,
            role=role_clean,
            queries=queries,
            total_unique_questions=len(items),
            questions=question_list,
            sources=sources[:max_sources],
            warnings=warnings,
            meta={"sources_considered": len(urls)},
        )


class _LLM(Protocol):
    def structured(self, *, messages: list[dict[str, str]], schema: type[PrepDoc]):  # noqa: ANN201
        ...

    def chat(self, *, messages: list[dict[str, str]]):  # noqa: ANN201
        ...


_JSON_BLOCK_RE = re.compile(r"\{.*\}", flags=re.DOTALL)


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
                    q=company, skip=0, limit=clamp_int(self.max_notes, lo=1, hi=20)
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
            num_questions=clamp_int(num_questions, lo=1, hi=50),
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

    Uses Alfred's Postgres-backed `DataStoreService`.
    """

    collection_name: str = settings.interview_prep_collection
    store: DataStoreService | None = None

    def __post_init__(self) -> None:
        self._store = self.store or DataStoreService(default_collection=self.collection_name)

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


class InterviewQuestionsServiceProtocol(Protocol):
    """Dependency-inversion interface for collecting interview questions."""

    def generate_report(
        self,
        company: str,
        *,
        role: str | None = None,
        max_sources: int = 12,
        max_questions: int = 60,
        use_firecrawl_search: bool = True,
    ) -> InterviewQuestionsReport: ...


class CompanyResearchServiceProtocol(Protocol):
    """Dependency-inversion interface for generating company research reports."""

    def generate_report(self, company: str, *, refresh: bool = False) -> dict[str, Any]: ...


class PanelInterviewServiceProtocol(Protocol):
    """Dependency-inversion interface for running panel interview practice sessions."""

    def create_session(self, payload: PanelSessionCreate) -> PanelSession: ...

    def submit_turn(self, session_id: str, payload: PanelTurnRequest) -> PanelTurnResponse: ...


logger = logging.getLogger(__name__)


class InterviewAgentState(TypedDict):
    operation: UnifiedInterviewOperation
    company: str
    role: str
    max_sources: int
    max_questions: int
    use_firecrawl: bool
    include_deep_research: bool
    target_length_words: int
    candidate_background: str | None
    candidate_response: str | None
    session_id: str | None

    raw_questions: list[dict[str, Any]]
    validated_questions: list[dict[str, Any]]
    questions_with_solutions: list[dict[str, Any]]
    sources_scraped: int

    company_research: dict[str, Any]
    research_report: str

    practice_events: list[dict[str, Any]]
    errors: list[str]


def _safe_text(value: object) -> str:
    return str(value or "").strip()


def _append_error(state: InterviewAgentState, message: str) -> list[str]:
    errs = list(state.get("errors") or [])
    errs.append(message)
    return errs


def _normalize_question_item(item: QuestionItem) -> dict[str, Any]:
    return {
        "question": item.question,
        "categories": list(item.categories or []),
        "occurrences": item.occurrences,
        "sources": list(item.sources or []),
    }


def _extract_company_key_insights(doc: dict[str, Any], *, limit: int = 8) -> list[str]:
    report = doc.get("report") or {}
    sections = report.get("sections") or []
    insights: list[str] = []
    for section in sections:
        for item in section.get("insights") or []:
            text = _safe_text(item)
            if text:
                insights.append(text)
    # De-duplicate while preserving order
    unique = list(dict.fromkeys(insights))
    return unique[: max(0, int(limit))]


def _should_use_dspy() -> bool:
    if settings.app_env in {"test", "ci"}:
        return False
    if settings.llm_provider != LLMProvider.openai:
        return False
    if not settings.openai_api_key:
        return False
    return True


@lru_cache(maxsize=1)
def _configure_dspy_lm() -> bool:
    """Best-effort DSPy configuration. Returns True if configured; otherwise False."""

    if not _should_use_dspy():
        return False

    try:
        import dspy
    except Exception as exc:  # pragma: no cover - optional runtime guard
        logger.info("DSPy unavailable: %s", exc)
        return False

    api_key = settings.openai_api_key.get_secret_value() if settings.openai_api_key else None
    if not api_key:
        return False

    model_name = _safe_text(settings.llm_model) or "gpt-4.1-mini"
    model = model_name if "/" in model_name else f"openai/{model_name}"

    # DSPy enforces constraints for OpenAI reasoning models (o1/o3/o4/gpt-5 family).
    # Keep defaults permissive to avoid runtime ValueErrors.
    lm_kwargs: dict[str, Any] = {"api_key": api_key, "cache": False}
    if settings.openai_base_url:
        lm_kwargs["base_url"] = settings.openai_base_url
    if settings.openai_organization:
        lm_kwargs["organization"] = settings.openai_organization

    try:
        lm = dspy.LM(model, temperature=None, max_tokens=None, **lm_kwargs)
        dspy.configure(lm=lm)
        return True
    except Exception as exc:  # pragma: no cover - provider misconfig
        logger.info("DSPy configure failed: %s", exc)
        return False


def _dspy_modules():
    """Create DSPy modules lazily (only when LLM is configured)."""

    if not _configure_dspy_lm():
        return None

    import dspy

    class QuestionValidator(dspy.Signature):
        """Validate whether a string is a plausible real interview question."""

        question: str = dspy.InputField(desc="Interview question to validate")
        company: str = dspy.InputField(desc="Company name for context")
        role: str = dspy.InputField(desc="Role for context")

        is_valid: bool = dspy.OutputField(desc="True if likely a legitimate interview question")
        confidence: float = dspy.OutputField(desc="Confidence score 0-1")
        reasoning: str = dspy.OutputField(desc="Brief reasoning for validity")

    class SolutionGenerator(dspy.Signature):
        """Generate a concise sample solution/answer for an interview question."""

        question: str = dspy.InputField(desc="Interview question")
        question_type: str = dspy.InputField(desc="coding | behavioral | system_design | general")
        difficulty: str = dspy.InputField(desc="easy | medium | hard")
        candidate_background: str = dspy.InputField(
            desc="Optional candidate background; use sparingly to tailor examples"
        )

        solution: str = dspy.OutputField(desc="Sample solution/answer with explanation")
        time_complexity: str = dspy.OutputField(desc="Time complexity if applicable; else 'N/A'")
        space_complexity: str = dspy.OutputField(desc="Space complexity if applicable; else 'N/A'")
        key_insights: list[str] = dspy.OutputField(desc="Key insights bullets")

    return {
        "validator": dspy.ChainOfThought(QuestionValidator),
        "solver": dspy.ChainOfThought(SolutionGenerator),
    }


def _pick_question_type(categories: list[str]) -> str:
    cats = {c.strip().lower() for c in categories if c}
    if "coding" in cats:
        return "coding"
    if "system_design" in cats:
        return "system_design"
    if "behavioral" in cats:
        return "behavioral"
    if "ml_ai" in cats:
        return "coding"
    return "general"


def _compile_report_markdown(
    *,
    company: str,
    role: str,
    company_research: dict[str, Any] | None,
    questions: list[dict[str, Any]],
    target_length_words: int,
) -> str:
    report_doc = company_research or {}
    report = report_doc.get("report") or {}

    lines: list[str] = [
        f"# Interview Preparation Report: {company} — {role}",
        "",
    ]

    exec_summary = _safe_text(report.get("executive_summary"))
    if exec_summary:
        lines.extend(["## Company Overview", exec_summary, ""])

    sections = report.get("sections") or []
    if sections:
        lines.append("## Company Insights")
        for section in sections[:6]:
            name = _safe_text(section.get("name")) or "Insights"
            summary = _safe_text(section.get("summary"))
            if not summary:
                continue
            lines.extend([f"### {name}", summary, ""])
        lines.append("")

    # Heuristic sizing: keep the report roughly within the requested length.
    # More words -> include more questions, up to a sane cap.
    base = clamp_int(target_length_words // 120, lo=6, hi=25)
    limit_questions = clamp_int(base, lo=1, hi=max(1, len(questions)))

    lines.append("## Interview Questions (with sample solutions)")
    for idx, q in enumerate(questions[:limit_questions], start=1):
        q_text = _safe_text(q.get("question")) or "N/A"
        cats = q.get("categories") or []
        lines.extend([f"### Q{idx}. {q_text}", f"**Category:** {', '.join(cats) or 'General'}"])

        sol = q.get("solution") or {}
        approach = _safe_text(sol.get("approach"))
        if approach:
            lines.extend(["", "#### Sample answer / solution", approach, ""])
            tc = _safe_text(sol.get("time_complexity")) or "N/A"
            sc = _safe_text(sol.get("space_complexity")) or "N/A"
            lines.extend([f"**Time complexity:** {tc}", f"**Space complexity:** {sc}", ""])

        insights = sol.get("key_insights") or []
        if isinstance(insights, list) and insights:
            lines.append("**Key insights:**")
            for item in insights[:6]:
                text = _safe_text(item)
                if text:
                    lines.append(f"- {text}")
            lines.append("")

    return "\n".join(lines).strip()


@dataclass
class UnifiedInterviewAgent:
    """Orchestrates interview question collection, deep research, and practice sessions."""

    questions_service: InterviewQuestionsServiceProtocol
    company_research_service: CompanyResearchServiceProtocol
    panel_service: PanelInterviewServiceProtocol | None = None

    def __post_init__(self) -> None:
        self._graph = self._build_graph()

    def _build_graph(self):
        graph = StateGraph(InterviewAgentState)

        graph.add_node("route", self._route_node)
        graph.add_node("research_company", self._research_company_node)
        graph.add_node("collect_questions", self._collect_questions_node)
        graph.add_node("validate_questions", self._validate_questions_node)
        graph.add_node("generate_solutions", self._generate_solutions_node)
        graph.add_node("compile_report", self._compile_report_node)
        graph.add_node("practice_session", self._practice_session_node)

        graph.add_edge(START, "route")
        graph.add_conditional_edges(
            "route",
            self._route_operation,
            {
                "collect_questions": "collect_questions",
                "deep_research": "research_company",
                "practice_session": "practice_session",
            },
        )

        graph.add_edge("research_company", "collect_questions")
        graph.add_edge("collect_questions", "validate_questions")
        graph.add_edge("validate_questions", "generate_solutions")
        graph.add_conditional_edges(
            "generate_solutions",
            self._route_after_solutions,
            {"compile_report": "compile_report", END: END},
        )
        graph.add_edge("compile_report", END)
        graph.add_edge("practice_session", END)

        return graph.compile()

    @staticmethod
    def _route_node(state: InterviewAgentState) -> dict[str, Any]:
        # Identity node; kept for readability and to allow conditional entry routing.
        return dict(state)

    @staticmethod
    def _route_operation(state: InterviewAgentState) -> UnifiedInterviewOperation:
        return state["operation"]

    @staticmethod
    def _route_after_solutions(state: InterviewAgentState) -> Literal["compile_report", "__end__"]:
        if state.get("operation") == "deep_research":
            return "compile_report"
        return END

    async def _research_company_node(self, state: InterviewAgentState) -> dict[str, Any]:
        if not state.get("include_deep_research", True):
            return {"company_research": {}}

        try:
            doc = await run_in_threadpool(
                self.company_research_service.generate_report,
                state["company"],
                refresh=False,
            )
            if isinstance(doc, dict):
                return {"company_research": doc}
        except Exception as exc:  # pragma: no cover - network/provider errors
            return {"errors": _append_error(state, f"Company research failed: {exc}")}

        return {"company_research": {}}

    async def _collect_questions_node(self, state: InterviewAgentState) -> dict[str, Any]:
        try:
            report: InterviewQuestionsReport = await run_in_threadpool(
                self.questions_service.generate_report,
                state["company"],
                role=state.get("role"),
                max_sources=state.get("max_sources", 12),
                max_questions=state.get("max_questions", 60),
                use_firecrawl_search=state.get("use_firecrawl", True),
            )
            raw = [_normalize_question_item(item) for item in report.questions]
            return {"raw_questions": raw, "sources_scraped": len(report.sources)}
        except Exception as exc:  # pragma: no cover - network/provider errors
            return {"errors": _append_error(state, f"Question collection failed: {exc}")}

    async def _validate_questions_node(self, state: InterviewAgentState) -> dict[str, Any]:
        raw = list(state.get("raw_questions") or [])
        if not raw:
            return {"validated_questions": []}

        modules = _dspy_modules()
        if modules is None:
            # Fallback: treat collected questions as already normalized and valid.
            return {"validated_questions": raw}

        validator = modules["validator"]
        validated: list[dict[str, Any]] = []
        for q in raw:
            q_text = _safe_text(q.get("question"))
            if not q_text:
                continue
            try:
                result = validator(question=q_text, company=state["company"], role=state["role"])
                is_valid = bool(getattr(result, "is_valid", False))
                confidence = float(getattr(result, "confidence", 0.0) or 0.0)
                reasoning = _safe_text(getattr(result, "reasoning", "")) or ""
                if is_valid and confidence >= 0.7:
                    validated.append(
                        {
                            **q,
                            "validation": {
                                "is_valid": True,
                                "confidence": confidence,
                                "reasoning": reasoning,
                            },
                        }
                    )
            except Exception as exc:  # pragma: no cover - provider/runtime issues
                # If validation becomes flaky, keep going and fall back to raw at the end.
                state["errors"] = _append_error(state, f"Question validation failed: {exc}")

        # If the validator filtered too aggressively, fall back to the original set.
        if not validated:
            validated = raw
        return {"validated_questions": validated, "errors": list(state.get("errors") or [])}

    async def _generate_solutions_node(self, state: InterviewAgentState) -> dict[str, Any]:
        validated = list(state.get("validated_questions") or [])
        if not validated:
            return {"questions_with_solutions": []}

        modules = _dspy_modules()
        if modules is None:
            # Fallback: keep questions but omit solutions.
            return {"questions_with_solutions": validated}

        solver = modules["solver"]

        # Keep costs bounded; solution generation can be expensive.
        max_items = min(20, len(validated))
        with_solutions: list[dict[str, Any]] = []

        for q in validated[:max_items]:
            q_text = _safe_text(q.get("question"))
            if not q_text:
                continue
            cats = q.get("categories") or []
            q_type = _pick_question_type(cats if isinstance(cats, list) else [])

            try:
                result = solver(
                    question=q_text,
                    question_type=q_type,
                    difficulty="medium",
                    candidate_background=_safe_text(state.get("candidate_background")) or "N/A",
                )

                key_insights = getattr(result, "key_insights", []) or []
                if not isinstance(key_insights, list):
                    key_insights = [_safe_text(key_insights)] if _safe_text(key_insights) else []

                with_solutions.append(
                    {
                        **q,
                        "solution": {
                            "approach": _safe_text(getattr(result, "solution", "")),
                            "time_complexity": _safe_text(getattr(result, "time_complexity", "")),
                            "space_complexity": _safe_text(getattr(result, "space_complexity", "")),
                            "key_insights": [_safe_text(x) for x in key_insights if _safe_text(x)],
                        },
                    }
                )
            except Exception as exc:  # pragma: no cover - provider/runtime issues
                with_solutions.append(q)
                state["errors"] = _append_error(state, f"Solution generation failed: {exc}")

        # Include any validated questions beyond the capped solution generation.
        with_solutions.extend(validated[max_items:])
        return {
            "questions_with_solutions": with_solutions,
            "errors": list(state.get("errors") or []),
        }

    async def _compile_report_node(self, state: InterviewAgentState) -> dict[str, Any]:
        report = _compile_report_markdown(
            company=state["company"],
            role=state["role"],
            company_research=state.get("company_research") or {},
            questions=list(state.get("questions_with_solutions") or []),
            target_length_words=state.get("target_length_words", 1000),
        )
        return {"research_report": report}

    async def _practice_session_node(self, state: InterviewAgentState) -> dict[str, Any]:
        if self.panel_service is None:
            return {
                "errors": _append_error(
                    state, "Panel interview service is not configured for practice sessions."
                )
            }

        try:
            session_id = state.get("session_id")
            if not session_id:
                session = self.panel_service.create_session(
                    PanelSessionCreate(
                        config=PanelConfig(company=state["company"], role=state["role"]),
                        candidate_context=_safe_text(state.get("candidate_background")) or None,
                    )
                )
                session_id = session.id

            events: list[dict[str, Any]] = []
            if state.get("candidate_response"):
                resp = self.panel_service.submit_turn(
                    session_id, PanelTurnRequest(answer=_safe_text(state.get("candidate_response")))
                )
                events = [e.model_dump(mode="json") for e in resp.events]

            return {"session_id": session_id, "practice_events": events}
        except Exception as exc:  # pragma: no cover - storage/runtime issues
            return {"errors": _append_error(state, f"Practice session failed: {exc}")}

    async def process(self, request: UnifiedInterviewRequest) -> UnifiedInterviewResponse:
        """Execute the unified interview workflow and normalize the result shape."""

        company = _safe_text(request.company)
        role = _safe_text(request.role) or "Software Engineer"
        if not company:
            raise ValueError("company is required")

        initial_state: InterviewAgentState = {
            "operation": request.operation,
            "company": company,
            "role": role,
            "max_sources": request.max_sources,
            "max_questions": request.max_questions,
            "use_firecrawl": request.use_firecrawl,
            "include_deep_research": request.include_deep_research,
            "target_length_words": request.target_length_words,
            "candidate_background": request.candidate_background,
            "candidate_response": request.candidate_response,
            "session_id": request.session_id,
            "raw_questions": [],
            "validated_questions": [],
            "questions_with_solutions": [],
            "sources_scraped": 0,
            "company_research": {},
            "research_report": "",
            "practice_events": [],
            "errors": [],
        }

        final_state: InterviewAgentState = await self._graph.ainvoke(initial_state)

        questions: list[UnifiedQuestion] | None = None
        if request.operation in {"collect_questions", "deep_research"}:
            questions = []
            for q in final_state.get("questions_with_solutions") or []:
                try:
                    questions.append(UnifiedQuestion.model_validate(q))
                except Exception:
                    continue

        interviewer_response: str | None = None
        if request.operation == "practice_session":
            # The panel simulator returns events including the next question after an answer.
            for evt in reversed(final_state.get("practice_events") or []):
                if (evt.get("type") == "question") and _safe_text(evt.get("text")):
                    interviewer_response = _safe_text(evt.get("text"))
                    break

        key_insights = (
            _extract_company_key_insights(final_state.get("company_research") or {})
            if request.operation == "deep_research"
            else None
        )

        return UnifiedInterviewResponse(
            operation=request.operation,
            questions=questions,
            sources_scraped=final_state.get("sources_scraped"),
            research_report=final_state.get("research_report") or None
            if request.operation == "deep_research"
            else None,
            key_insights=key_insights,
            session_id=final_state.get("session_id"),
            interviewer_response=interviewer_response,
            feedback=None,
            metadata={
                "errors": list(final_state.get("errors") or []),
                "total_questions_collected": len(final_state.get("raw_questions") or []),
                "validated_count": len(final_state.get("validated_questions") or []),
            },
        )


__all__ = [
    "InterviewDetection",
    "InterviewDetectionService",
    "InterviewQuestionsService",
    "InterviewChecklistService",
    "InterviewPrepDocGenerator",
    "InterviewPrepRenderer",
    "InterviewPrepService",
    "InterviewQuizGenerator",
    "UnifiedInterviewAgent",
]
