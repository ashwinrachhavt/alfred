from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

_SUBJECT_COMPANY_RE = re.compile(
    r"(?i)\b(?:interview|phone screen|screening|onsite|on-site|technical)\b.*?\b(?:with|at)\s+([^|–—-]+)"
)
_SUBJECT_ROLE_RE = re.compile(r"(?i)\b(?:for|role|position)\s*[:\-]?\s*([^|–—]+)")

_MEETING_LINK_RE = re.compile(
    r"(https?://[^\s)]+)",
    re.IGNORECASE,
)

_KNOWN_MEETING_HOSTS = (
    "meet.google.com",
    "zoom.us",
    "teams.microsoft.com",
    "webex.com",
    "chime.aws",
)


def _extract_meeting_links(text: str) -> list[str]:
    urls = [m.group(1).strip() for m in _MEETING_LINK_RE.finditer(text or "")]
    out: list[str] = []
    for url in urls:
        if any(host in url for host in _KNOWN_MEETING_HOSTS):
            out.append(url)
    # stable order, de-duped
    return list(dict.fromkeys(out))


def _guess_interview_type(text: str) -> Optional[str]:
    t = (text or "").lower()
    if "onsite" in t or "on-site" in t:
        return "onsite"
    if "phone screen" in t or "phone call" in t or "phone interview" in t:
        return "phone"
    if "video" in t or "zoom" in t or "google meet" in t or "teams" in t:
        return "video"
    return None


def _parse_any_datetime(text: str) -> Optional[datetime]:
    """Best-effort datetime parsing without extra dependencies.

    Currently supports ISO timestamps embedded in the text.
    """
    t = text or ""
    m = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?(Z|[+-]\d{2}:\d{2})", t)
    if not m:
        # Fallback: try python-dateutil for common human formats on candidate substrings.
        try:
            from dateutil.parser import parse as dt_parse  # type: ignore

            candidates: list[str] = []
            candidates.extend(
                re.findall(
                    r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2}(?:,\s*\d{4})?(?:\s+\d{1,2}:\d{2}\s*(?:AM|PM)?)?\b",
                    t,
                    flags=re.IGNORECASE,
                )
            )
            candidates.extend(
                re.findall(
                    r"\b\d{1,2}/\d{1,2}/\d{2,4}(?:\s+\d{1,2}:\d{2}\s*(?:AM|PM)?)?\b",
                    t,
                    flags=re.IGNORECASE,
                )
            )
            candidates.extend(
                re.findall(
                    r"\b\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2}(:\d{2})?)?\b",
                    t,
                    flags=re.IGNORECASE,
                )
            )
            for cand in candidates[:5]:
                dt = dt_parse(cand, fuzzy=True, default=datetime.now(timezone.utc))
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
        except Exception:
            return None
    try:
        dt = datetime.fromisoformat(m.group(0).replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


@dataclass(frozen=True)
class InterviewDetectionResult:
    company: Optional[str] = None
    role: Optional[str] = None
    interview_type: Optional[str] = None
    interview_date: Optional[datetime] = None
    meeting_links: list[str] | None = None


class InterviewDetectionService:
    """Heuristics-based interview email parsing.

    This intentionally avoids network calls and does not attempt perfect NLP. It
    extracts the most actionable fields when present and leaves unknowns blank.
    """

    def detect(
        self,
        *,
        email_text: str,
        subject: str | None = None,
        company_hint: str | None = None,
        role_hint: str | None = None,
    ) -> InterviewDetectionResult:
        text = (email_text or "").strip()
        subj = (subject or "").strip()
        blob = f"{subj}\n\n{text}".strip()

        company = (company_hint or "").strip() or None
        role = (role_hint or "").strip() or None
        if (company is None or role is None) and subj:
            if company is None:
                m = _SUBJECT_COMPANY_RE.search(subj)
                if m:
                    raw_company = m.group(1).strip()
                    # Trim common follow-on like "for <role>"
                    raw_company = re.split(r"(?i)\s+\bfor\b\s+", raw_company, maxsplit=1)[0].strip()
                    company = raw_company or None
            if role is None:
                m = _SUBJECT_ROLE_RE.search(subj)
                if m:
                    role = m.group(1).strip() or None

        interview_type = _guess_interview_type(blob)
        interview_date = _parse_any_datetime(blob)
        meeting_links = _extract_meeting_links(blob)

        return InterviewDetectionResult(
            company=company,
            role=role,
            interview_type=interview_type,
            interview_date=interview_date,
            meeting_links=meeting_links,
        )

    def is_interview_candidate(self, *, email_text: str, subject: str | None = None) -> bool:
        """Heuristic filter to avoid processing unrelated emails."""
        blob = f"{(subject or '').lower()}\n{(email_text or '').lower()}"
        keywords = (
            "interview",
            "phone screen",
            "screening",
            "onsite",
            "on-site",
            "technical",
            "recruiter",
            "schedule",
            "availability",
        )
        return any(k in blob for k in keywords) or any(
            host in blob for host in ("meet.google.com", "zoom.us", "teams.microsoft.com")
        )


__all__ = ["InterviewDetectionResult", "InterviewDetectionService"]
